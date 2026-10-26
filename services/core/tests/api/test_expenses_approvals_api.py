"""报销、票据、审批接口（接口契约 §5、§6）。"""

import uuid

from fastapi.testclient import TestClient

from seed.business_data import E_MINGLI
from seed.data import C_MINGLI, C_PC3H
from seed.files import invoice_pdf, receipt_png
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker

PDF = invoice_pdf("Invoice T", "1.00")
PNG = receipt_png(8, 8)


def new_expense(
    client: TestClient, tracker: Tracker, amount: int = 40_000, headcount: int = 4, **extra: object
) -> dict:
    body = {
        "type": "entertainment",
        "amount": amount,
        "headcount": headcount,
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
    eid = new_expense(client, tracker, type="hotel", amount=58_000, headcount=1)["id"]
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
    client.post(f"/api/approvals/{aid}/decide", json={"decision": "reject"}, headers=MANAGER_H)
    assert (
        client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]["status"] == "rejected"
    )


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
