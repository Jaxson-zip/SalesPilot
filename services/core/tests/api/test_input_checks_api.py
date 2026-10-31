"""输入校验与统计口径：报销不能被错误自动通过、名称 / 电话统一校验、赢单金额与合同一致。"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.errors import BizError
from app.crm.models import Contract, Expense, Opportunity, Quote
from app.crm.services.codes import local_today
from app.crm.services.expense_service import ensure_complete
from seed.data import C_MINGLI
from tests.api.conftest import SALES_H, Tracker
from tests.api.test_expenses_approvals_api import PDF, new_expense, upload
from tests.api.test_opportunities_api import new_opp
from tests.api.test_sales_flow_api import _quote

TOMORROW = (local_today() + timedelta(days=1)).isoformat()


def _bad(r, message: str) -> None:
    body = r.json()
    assert body["code"] == 40001, r.text
    assert body["message"] == message


# ---------- 报销 ----------


def test_expense_rejects_blank_reason_and_future_date(client: TestClient, tracker: Tracker) -> None:
    base = {
        "type": "transport",
        "amount": 10_000,
        "occurred_on": local_today().isoformat(),
        "reason": "去客户现场",
    }
    _bad(
        client.post("/api/expenses", json={**base, "reason": "   "}, headers=SALES_H),
        "事由不能为空",
    )
    _bad(
        client.post("/api/expenses", json={**base, "occurred_on": "2099-01-01"}, headers=SALES_H),
        "发生日期不能晚于今天",
    )
    hotel = {
        **base,
        "type": "hotel",
        "details": {"city": "北京", "check_in": local_today().isoformat(), "check_out": TOMORROW},
    }
    _bad(
        client.post("/api/expenses", json=hotel, headers=SALES_H),
        "离店日期不能晚于今天，住完再报销",
    )
    # 修改走同一套校验
    e = new_expense(client, tracker)
    r = client.put(f"/api/expenses/{e['id']}", json={**base, "reason": " "}, headers=SALES_H)
    _bad(r, "事由不能为空")


def test_submit_rechecks_saved_expense() -> None:
    """数据是校验加上之前存进去的：提交时也拦下，不会自动通过。"""
    blank = Expense(type="transport", reason="  ", occurred_on=local_today(), details=None)
    with pytest.raises(BizError, match="事由不能为空"):
        ensure_complete(blank)
    future = Expense(type="transport", reason="打车", occurred_on=date(2099, 1, 1), details=None)
    with pytest.raises(BizError, match="发生日期不能晚于今天"):
        ensure_complete(future)
    ensure_complete(Expense(type="transport", reason="打车", occurred_on=local_today()))


def test_other_type_needs_manager_approval(client: TestClient, tracker: Tracker) -> None:
    """「其他」类费用制度里没有标准：不自动通过，交主管审核。"""
    e = new_expense(client, tracker, type="other", amount=20_000, headcount=1)
    assert e["policy_check"]["passed"] is False
    assert upload(client, e["id"], "invoice", "发票.pdf", PDF, "application/pdf")["code"] == 0
    r = client.post(f"/api/expenses/{e['id']}/submit", headers=SALES_H)
    assert r.json()["data"]["status"] == "pending_approval", r.text
    # 要审核但没有超出金额标准：不标「超标」，「只看超标」也筛不出来
    items = client.get("/api/expenses?over=yes&page_size=100", headers=SALES_H).json()["data"]
    assert e["id"] not in [i["id"] for i in items["items"]]
    mine = client.get("/api/expenses?type=other&page_size=100", headers=SALES_H).json()["data"]
    assert next(i for i in mine["items"] if i["id"] == e["id"])["over_limit"] is False
    # 交通费照旧实报实销
    t = new_expense(client, tracker, type="transport", amount=20_000, headcount=1)
    assert t["policy_check"]["passed"] is True


# ---------- 客户 / 联系人 ----------


def test_customer_and_contact_names_and_phone(client: TestClient) -> None:
    _bad(client.post("/api/customers", json={"name": "   "}, headers=SALES_H), "客户名称不能为空")
    _bad(
        client.patch(f"/api/customers/{C_MINGLI}", json={"name": " "}, headers=SALES_H),
        "客户名称不能为空",
    )
    url = f"/api/customers/{C_MINGLI}/contacts"
    _bad(client.post(url, json={"name": "  "}, headers=SALES_H), "联系人姓名不能为空")
    r = client.post(url, json={"name": "测试", "phone": "abc"}, headers=SALES_H)
    assert r.json()["code"] == 40001 and "电话格式不对" in r.json()["message"]
    _bad(
        client.post("/api/opportunities", json={"customer_id": str(C_MINGLI), "name": " "},
                    headers=SALES_H),
        "商机名称不能为空",
    )  # fmt: skip


def test_import_checks_phone(client: TestClient) -> None:
    body = "客户名称*,联系人,电话\n导入电话测试公司,王总,abc\n"
    files = {"file": ("c.csv", body.encode("utf-8"), "text/csv")}
    r = client.post("/api/customers/import/preview", files=files, headers=SALES_H)
    row = r.json()["data"]["rows"][0]
    assert row["status"] == "error" and "电话格式不对" in row["message"]


# ---------- 赢单金额与合同 ----------


def _won(client: TestClient) -> dict:
    funnel = client.get("/api/dashboard", headers=SALES_H).json()["data"]["funnel"]
    return next(s for s in funnel if s["stage"] == "won")


def test_won_amount_follows_contract(client: TestClient, tracker: Tracker) -> None:
    before = _won(client)
    opp = new_opp(client, tracker, amount=1_000_000)
    quote = _quote(tracker, opp["id"])
    url = f"/api/opportunities/{opp['id']}"
    r = client.patch(f"{url}/stage", json={"stage": "won"}, headers=SALES_H)
    assert r.status_code == 200, r.text
    # 手工标赢单、还没有合同：漏斗上单独提示，不算本月成交
    mid = _won(client)
    assert mid["unsigned_count"] == before["unsigned_count"] + 1
    assert mid["unsigned_amount"] == before["unsigned_amount"] + 1_000_000

    from app.common.db import session_scope

    with session_scope() as db:
        db.get(Quote, quote.id).status = "sent"  # type: ignore[union-attr]
    assert client.post(f"/api/quotes/{quote.id}/accept", headers=SALES_H).status_code == 200
    with session_scope() as db:
        contract = db.scalar(select(Contract).where(Contract.quote_id == quote.id))
        assert contract is not None
        amount = db.get(Opportunity, uuid.UUID(opp["id"])).amount  # type: ignore[union-attr]
        assert amount == contract.amount != 1_000_000
    after = _won(client)
    assert after["unsigned_count"] == before["unsigned_count"]
    # 签了合同之后金额按合同算，不能再手改
    r = client.patch(url, json={"amount": 5}, headers=SALES_H)
    assert r.json()["code"] == 42201 and "按合同金额计" in r.json()["message"]


def test_website_only_http(client: TestClient) -> None:
    for bad in ("javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,x", "//evil.com"):
        r = client.post(
            "/api/customers", json={"name": "网站测试", "website": bad}, headers=SALES_H
        )
        assert r.json()["code"] == 40001 and "http://" in r.json()["message"], bad
        r = client.patch(f"/api/customers/{C_MINGLI}", json={"website": bad}, headers=SALES_H)
        assert r.json()["code"] == 40001, bad
    body = "客户名称*,网站\n网站导入测试公司,javascript:alert(1)\n"
    files = {"file": ("c.csv", body.encode("utf-8"), "text/csv")}
    row = client.post("/api/customers/import/preview", files=files, headers=SALES_H).json()
    assert row["data"]["rows"][0]["status"] == "error"
