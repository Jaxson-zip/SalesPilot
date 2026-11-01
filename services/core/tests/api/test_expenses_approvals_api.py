"""报销、票据、审批接口（接口契约 §5、§6）。"""

import uuid

from fastapi.testclient import TestClient

from app.crm.services.demo import demo_id
from seed.business_data import E_MINGLI
from seed.data import C_MINGLI, C_PC3H
from seed.files import invoice_pdf, receipt_png
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker

PDF = invoice_pdf("Invoice T", "1.00")
PNG = receipt_png(8, 8)
CONTACT_WANG = demo_id("contact:mingli:wang")


def new_expense(
    client: TestClient, tracker: Tracker, amount: int = 40_000, headcount: int = 4, **extra: object
) -> dict:
    """headcount 由后端计算（契约 v3 §17）：招待 = 王律师 + 本人 + 其他人数。"""
    entertainment = extra.get("type", "entertainment") == "entertainment"
    known = 2 if entertainment else 1
    body = {
        "type": "entertainment",
        "amount": amount,
        "contact_ids": [str(CONTACT_WANG)] if entertainment else [],
        "extra_guests": headcount - known,
        "occurred_on": "2026-10-24",
        "customer_id": str(C_MINGLI),
        "reason": "测试-方案沟通晚餐",
        "idempotency_key": uuid.uuid4().hex,
        **extra,
    }
    r = client.post("/api/expenses", json=body, headers=SALES_H)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    tracker.expenses.append(uuid.UUID(data["id"]))
    return data


def upload(client: TestClient, eid: str, kind: str, name: str, content: bytes, mime: str) -> dict:
    files = {"file": (name, content, mime)}
    r = client.post(
        f"/api/expenses/{eid}/attachments", files=files, data={"kind": kind}, headers=SALES_H
    )
    return r.json()


def with_receipts(client: TestClient, eid: str) -> None:
    assert upload(client, eid, "invoice", "发票.pdf", PDF, "application/pdf")["code"] == 0
    assert upload(client, eid, "receipt", "小票.png", PNG, "image/png")["code"] == 0


def test_create_stores_policy_check(client: TestClient, tracker: Tracker) -> None:
    e = new_expense(client, tracker, amount=86_000)
    assert e["status"] == "draft" and e["code"].startswith("E-") and e["over_limit"]
    assert e["policy_check"] == {
        "passed": False,
        "per_person": 21_500,
        "limit_per_person": 15_000,
        "over_amount": 26_000,
        "rule_ref": "《费用报销管理制度》4.2 招待标准",
        "unit": "person",
    }
    assert e["customer"]["name"] == "深圳明理律师事务所" and e["attachments"] == []


def test_create_validation_and_idempotency(client: TestClient, tracker: Tracker) -> None:
    e = new_expense(client, tracker)
    key = {"idempotency_key": uuid.uuid4().hex}
    bad = client.post("/api/expenses", json={"type": "travel", "amount": 0, **key}, headers=SALES_H)
    assert bad.json()["code"] == 40001
    with_key = client.get(f"/api/expenses/{e['id']}", headers=SALES_H).json()["data"]
    assert with_key["id"] == e["id"]
    body = {"type": "transport", "amount": 100, "occurred_on": "2026-10-24", "reason": "测试-重复"}
    first = client.post("/api/expenses", json={**body, **key}, headers=SALES_H).json()
    tracker.expenses.append(uuid.UUID(first["data"]["id"]))
    dup = client.post("/api/expenses", json={**body, **key}, headers=SALES_H)
    assert dup.status_code == 409 and dup.json()["code"] == 40901


def test_create_with_invisible_customer(client: TestClient) -> None:
    body = {"type": "transport", "amount": 100, "occurred_on": "2026-10-24", "reason": "测试",
            "customer_id": str(C_PC3H)}  # fmt: skip
    assert client.post("/api/expenses", json=body, headers=SALES_H).json()["code"] == 40401


def test_upload_validation(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker)["id"]
    assert (
        upload(client, eid, "invoice", "a.exe", b"MZ", "application/octet-stream")["code"] == 40001
    )
    # 扩展名伪装：内容不是 PDF
    assert upload(client, eid, "invoice", "a.pdf", b"MZ fake", "application/pdf")["code"] == 40001
    big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024)
    assert upload(client, eid, "invoice", "big.pdf", big, "application/pdf")["code"] == 40001
    assert upload(client, eid, "bad", "a.pdf", PDF, "application/pdf")["code"] == 40001
    ok = upload(client, eid, "invoice", "发票.pdf", PDF, "application/pdf")["data"]
    assert ok["mime"] == "application/pdf" and ok["url"] == f"/api/attachments/{ok['id']}/file"


def test_submit_requires_invoice_and_receipt(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker)["id"]
    r = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()
    assert r["code"] == 42201 and r["data"]["rule"] == "expense_missing_invoice"
    assert set(r["data"]["missing"]) == {"invoice", "receipt"}
    upload(client, eid, "invoice", "发票.pdf", PDF, "application/pdf")
    again = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()
    assert again["data"]["missing"] == ["receipt"]


def test_within_limit_auto_approved_and_idempotent(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker, amount=60_000, headcount=4)["id"]  # 人均 ¥150，刚好达标
    with_receipts(client, eid)
    data = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()["data"]
    assert data["status"] == "approved" and data["attachment_count"] == 2
    dup = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    assert dup.status_code == 409 and dup.json()["code"] == 40901
    att = data["attachments"][0]["id"]
    locked = client.delete(f"/api/attachments/{att}", headers=SALES_H).json()
    assert locked["code"] == 42201 and locked["data"]["rule"] == "expense_not_editable"


def test_non_entertainment_needs_only_invoice(client: TestClient, tracker: Tracker) -> None:
    stay = {"city": "深圳", "check_in": "2026-10-23", "check_out": "2026-10-24"}
    eid = new_expense(client, tracker, type="hotel", amount=48_000, headcount=1, details=stay)["id"]
    upload(client, eid, "invoice", "住宿发票.pdf", PDF, "application/pdf")
    assert (
        client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()["data"]["status"]
        == "approved"
    )


def test_over_limit_approval_flow(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker, amount=86_000)["id"]
    with_receipts(client, eid)
    assert (
        client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()["data"]["status"]
        == "pending_approval"
    )

    for headers in (SALES_H, ADMIN_H):
        r = client.get("/api/approvals", headers=headers)
        assert r.status_code == 403 and r.json()["code"] == 40301
    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H).json()[
        "data"
    ]
    approval = next(a for a in pending["items"] if a["target"]["id"] == eid)
    assert approval["target"]["amount"] == 86_000 and approval["target"]["owner"]["name"] == "张晨"
    assert len(approval["attachments"]) == 2 and "人均 ¥215" in approval["reason"]
    # 审批列表直接给出超标金额和发生日期（不用从文字里解析）
    assert approval["target"]["over_amount"] == 26_000 and approval["target"]["occurred_on"]
    assert approval["target"]["margin_rate"] is None

    url = f"/api/approvals/{approval['id']}/decide"
    assert client.post(url, json={"decision": "approve"}, headers=SALES_H).json()["code"] == 40301
    assert client.post(url, json={"decision": "maybe"}, headers=MANAGER_H).json()["code"] == 40001
    decided = client.post(url, json={"decision": "approve", "comment": "同意"}, headers=MANAGER_H)
    assert decided.json()["data"]["status"] == "approved"
    again = client.post(url, json={"decision": "reject"}, headers=MANAGER_H).json()
    assert again["code"] == 42201 and again["data"]["rule"] == "approval_already_decided"
    assert (
        client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]["status"] == "approved"
    )
    done = client.get("/api/approvals?status=done&page_size=100", headers=MANAGER_H).json()["data"]
    assert approval["id"] in {a["id"] for a in done["items"]}


def test_reject_expense(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker, amount=86_000)["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H).json()[
        "data"
    ]
    aid = next(a["id"] for a in pending["items"] if a["target"]["id"] == eid)
    url = f"/api/approvals/{aid}/decide"
    # 驳回必须写原因
    blank = client.post(url, json={"decision": "reject", "comment": " "}, headers=MANAGER_H)
    assert blank.json()["code"] == 40001
    reason = "人均超标，请按 4 人以内重新报"
    client.post(url, json={"decision": "reject", "comment": reason}, headers=MANAGER_H)
    e = client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]
    assert e["status"] == "rejected"
    # 员工能看到原因
    assert e["approvals"][-1]["status"] == "rejected" and e["approvals"][-1]["comment"] == reason


def test_resubmit_rejected_expense(client: TestClient, tracker: Tracker) -> None:
    """被驳回的报销单：改金额、补票据后在同一张单上重新提交，两轮审批都留在记录里。"""
    e = new_expense(client, tracker, amount=86_000)
    eid = e["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H).json()
    aid = next(a["id"] for a in pending["data"]["items"] if a["target"]["id"] == eid)
    body = {"decision": "reject", "comment": "超标部分自己承担"}
    client.post(f"/api/approvals/{aid}/decide", json=body, headers=MANAGER_H)

    # 别人改不了；本人改金额到标准以内
    edit = {
        "type": "entertainment",
        "amount": 60_000,
        "contact_ids": [str(CONTACT_WANG)],
        "extra_guests": 2,
        "occurred_on": "2026-10-24",
        "customer_id": str(C_MINGLI),
        "reason": "测试-方案沟通晚餐（超标部分自理）",
    }
    assert client.put(f"/api/expenses/{eid}", json=edit, headers=SALES2_H).json()["code"] == 40401
    changed = client.put(f"/api/expenses/{eid}", json=edit, headers=SALES_H).json()["data"]
    assert changed["status"] == "rejected" and changed["amount"] == 60_000
    assert not changed["over_limit"]
    # 驳回后还能补票据
    assert upload(client, eid, "other", "说明.png", PNG, "image/png")["code"] == 0

    again = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()["data"]
    assert again["status"] == "approved"
    assert [a["status"] for a in again["approvals"]] == ["rejected"]
    # 通过后不能再改
    locked = client.put(f"/api/expenses/{eid}", json=edit, headers=SALES_H).json()
    assert locked["code"] == 42201 and locked["data"]["rule"] == "expense_not_editable"


def test_decide_unknown_approval(client: TestClient) -> None:
    r = client.post(
        f"/api/approvals/{uuid.uuid4()}/decide", json={"decision": "approve"}, headers=MANAGER_H
    )
    assert r.json()["code"] == 40401


def test_download_and_delete_respect_scope(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker)["id"]
    att = upload(client, eid, "invoice", "发票.pdf", PDF, "application/pdf")["data"]
    mine = client.get(att["url"], headers=SALES_H)
    assert mine.status_code == 200 and mine.content.startswith(b"%PDF")
    assert mine.headers["content-type"] == "application/pdf"
    assert client.get(att["url"], headers=MANAGER_H).status_code == 200
    other = client.get(att["url"], headers=SALES2_H)
    assert other.status_code == 404 and other.json()["code"] == 40401
    assert client.delete(f"/api/attachments/{att['id']}", headers=SALES2_H).json()["code"] == 40401
    assert client.delete(f"/api/attachments/{att['id']}", headers=SALES_H).json()["code"] == 0
    assert client.get(att["url"], headers=SALES_H).json()["code"] == 40401


def test_list_and_demo_expense(client: TestClient) -> None:
    data = client.get("/api/expenses?status=pending_approval", headers=SALES_H).json()["data"]
    demo = next(e for e in data["items"] if e["id"] == str(E_MINGLI))
    assert demo["amount"] == 86_000 and demo["over_limit"] and demo["attachment_count"] == 2
    detail = client.get(f"/api/expenses/{E_MINGLI}", headers=SALES_H).json()["data"]
    assert {a["kind"] for a in detail["attachments"]} == {"invoice", "receipt"}
    assert detail["opportunity"]["name"] == "合同审查私有化"
    assert client.get(f"/api/expenses/{E_MINGLI}", headers=SALES2_H).json()["code"] == 40401
    assert client.get("/api/expenses", headers=SALES2_H).json()["data"]["total"] == 0
    assert client.get("/api/expenses?status=bad", headers=SALES_H).json()["code"] == 40001


HOTEL = {"type": "hotel", "headcount": 1, "customer_id": None, "reason": "测试-出差住宿"}


def test_hotel_over_standard_needs_approval(client: TestClient, tracker: Tracker) -> None:
    """一线城市 ¥500/晚：深圳 2 晚 ¥1,200 超出 ¥200，进入主管审批（制度 3.2）。"""
    stay = {"city": "深圳", "check_in": "2026-10-22", "check_out": "2026-10-24"}
    e = new_expense(client, tracker, amount=120_000, details=stay, **HOTEL)
    assert e["policy_check"]["unit"] == "night"
    assert e["policy_check"]["per_person"] == 60_000 and e["policy_check"]["over_amount"] == 20_000
    assert e["policy_check"]["rule_ref"] == "《费用报销管理制度》3.2 住宿"
    assert {k: v for k, v in e["details"].items() if v} == stay
    upload(client, e["id"], "invoice", "住宿发票.pdf", PDF, "application/pdf")
    r = client.post(f"/api/expenses/{e['id']}/submit", headers=SALES_H)
    assert r.json()["data"]["status"] == "pending_approval"


def test_hotel_requires_city_and_dates(client: TestClient) -> None:
    base = {**HOTEL, "amount": 30_000, "occurred_on": "2026-10-24"}
    r = client.post("/api/expenses", json=base, headers=SALES_H)
    assert r.status_code == 400 and r.json()["code"] == 40001
    assert r.json()["data"]["errors"][0]["loc"] == ["body", "details", "city"]
    bad = {"city": "长沙", "check_in": "2026-10-24", "check_out": "2026-10-24"}
    r = client.post("/api/expenses", json={**base, "details": bad}, headers=SALES_H)
    assert r.json()["data"]["errors"][0]["loc"] == ["body", "details", "check_out"]


def test_precheck_hotel_other_city(client: TestClient) -> None:
    stay = {"city": "长沙", "check_in": "2026-10-22", "check_out": "2026-10-24"}
    body = {"type": "hotel", "amount": 70_000, "details": stay}
    data = client.post("/api/expenses/precheck", json=body, headers=SALES_H).json()["data"]
    assert data["unit"] == "night" and data["limit_per_person"] == 35_000
    assert data["need_approval"] is False


def test_split_entertainment_goes_to_approval(client: TestClient, tracker: Tracker) -> None:
    """一顿 ¥1,200 / 4 人的饭拆成两张 ¥600：单张不超标，合并人均 ¥300 超标 → 第二张进审批。"""
    day = {"occurred_on": "2026-09-03"}
    first = new_expense(client, tracker, amount=60_000, **day)
    with_receipts(client, first["id"])
    r = client.post(f"/api/expenses/{first['id']}/submit", headers=SALES_H).json()
    assert r["data"]["status"] == "approved"
    second = new_expense(client, tracker, amount=60_000, **day)
    assert second["policy_check"]["passed"]  # 单看这一张不超标
    with_receipts(client, second["id"])
    r = client.post(f"/api/expenses/{second['id']}/submit", headers=SALES_H).json()
    data = r["data"]
    assert data["status"] == "pending_approval"
    assert data["policy_check"]["passed"] is False and data["policy_check"]["per_person"] == 30_000
    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H)
    approval = next(a for a in pending.json()["data"]["items"] if a["target"]["id"] == second["id"])
    assert first["code"] in approval["reason"] and "拆单" in approval["reason"]
    assert approval["target"]["over_amount"] == 60_000
    # 另一天的同类招待不受影响
    other = new_expense(client, tracker, amount=60_000, occurred_on="2026-09-04")
    with_receipts(client, other["id"])
    r = client.post(f"/api/expenses/{other['id']}/submit", headers=SALES_H).json()
    assert r["data"]["status"] == "approved"


def test_owner_can_remind_manager_once_per_half_hour(client: TestClient, tracker: Tracker) -> None:
    e = new_expense(client, tracker, amount=86_000, occurred_on="2026-09-05")
    body = {"target_type": "expense", "target_id": e["id"]}
    early = client.post("/api/approvals/remind", json=body, headers=SALES_H).json()
    assert early["code"] == 42201 and early["data"]["rule"] == "approval_not_pending"
    with_receipts(client, e["id"])
    client.post(f"/api/expenses/{e['id']}/submit", headers=SALES_H)
    assert client.post("/api/approvals/remind", json=body, headers=SALES2_H).json()["code"] != 0
    r = client.post("/api/approvals/remind", json=body, headers=SALES_H).json()
    assert r["code"] == 0 and r["data"]["notified"] >= 1
    # 回归：催办日志原来只有「催办审批」，看不出是哪张单子
    logs = client.get(
        "/api/audit-logs", params={"action": "approval.remind"}, headers=MANAGER_H
    ).json()["data"]["items"]
    hit = [i for i in logs if i["target_id"] == e["id"]]
    assert hit and hit[0]["target_name"] == e["code"] and hit[0]["target_type"] == "expense"
    notes = client.get("/api/notifications", headers=MANAGER_H).json()["data"]["items"]
    assert any(n["type"] == "approval_remind" and e["code"] in n["title"] for n in notes)
    again = client.post("/api/approvals/remind", json=body, headers=SALES_H).json()
    assert again["code"] == 42201 and "分钟后可以再催" in again["message"]


def test_opportunity_shows_its_expenses(client: TestClient, tracker: Tracker) -> None:
    """报销关联到商机后，商机详情能看到这单花了多少：审批中和已批准分开，草稿不算。"""
    from app.common.db import session_scope
    from app.crm.models import Expense
    from tests.api.test_opportunities_api import new_opp

    opp = new_opp(client, tracker)
    ids = [
        new_expense(client, tracker, amount=a, opportunity_id=opp["id"])["id"]
        for a in (30_000, 50_000, 7_000)
    ]
    with session_scope() as db:
        for eid, status in zip(ids, ("approved", "pending_approval", "draft"), strict=True):
            db.get(Expense, uuid.UUID(eid)).status = status  # type: ignore[union-attr]
    detail = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert detail["expenses"] == {"approved": 30_000, "pending": 50_000, "count": 2}


def test_opportunity_profit_subtracts_commission_and_expenses(
    client: TestClient, tracker: Tracker
) -> None:
    """这单赚多少 = 报价毛利 − 预估提成 − 跟单费用；成交前按最新报价估算，成交后按接受的报价。"""
    from tests.api.test_opportunities_api import new_opp
    from tests.api.test_quotes_contracts_api import GOOD, act, create_quote, make_tier

    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}"
    assert client.get(url, headers=SALES_H).json()["data"]["profit"] is None

    qid = create_quote(tracker, make_tier(GOOD), opp["id"])
    new_expense(client, tracker, amount=80_000, opportunity_id=opp["id"])
    eid = new_expense(client, tracker, amount=20_000, opportunity_id=opp["id"])["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)

    profit = client.get(url, headers=SALES_H).json()["data"]["profit"]
    # 报价 15 万、成本 9 万；提成 = 硬件 3% + 服务 8% = 7000；草稿报销不算
    assert profit["basis"] == "latest" and profit["quote_id"] == qid
    assert profit["gross"] == 6_000_000 and profit["commission"] == 700_000
    assert profit["expenses"] == 20_000
    assert profit["net"] == 6_000_000 - 700_000 - 20_000

    for action in ("submit", "send", "accept"):
        act(client, qid, action)
    assert client.get(url, headers=SALES_H).json()["data"]["profit"]["basis"] == "accepted"
