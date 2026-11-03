"""调整回款计划：已发生的业务不能被改掉（2026-11-03 财务审查的回归用例）。

原来已收齐、收了一部分的期次都能删、能改金额和日期，到账冲抵到哪一期会跟着变；
改计划也不用写原因，动态里只留新计划。合同列表补了「待开票」和当前应收的本期总额。
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.db import session_scope
from app.crm.models import Activity
from tests.api.conftest import MANAGER_H, SALES_H, Tracker
from tests.api.test_quotes_contracts_api import _accepted_contract


def _paid_contract(client: TestClient, tracker: Tracker) -> tuple[str, list[dict]]:
    """¥150,000 合同 30/60/10 三期，回款 ¥60,000：第一期收齐，第二期收了 ¥15,000。"""
    contract = _accepted_contract(client, tracker)
    cid = contract["id"]
    client.post(f"/api/contracts/{cid}/payments", json={"amount": 6_000_000}, headers=MANAGER_H)
    plan = client.get(f"/api/contracts/{cid}/payment-plan", headers=SALES_H).json()["data"]
    keys = ("name", "amount", "due_date")
    return cid, [{k: i[k] for k in keys} for i in plan["items"]]


def _put(client: TestClient, cid: str, items: list[dict], reason: str | None = None) -> dict:
    body = {"items": items, "reason": reason}
    return client.put(f"/api/contracts/{cid}/payment-plan", json=body, headers=SALES_H).json()


def test_paid_periods_are_locked(client: TestClient, tracker: Tracker) -> None:
    cid, (p1, p2, p3) = _paid_contract(client, tracker)
    why = "客户申请延期"
    moved = _put(client, cid, [{**p1, "due_date": "2099-01-01"}, p2, p3], why)
    assert moved["code"] == 42201 and moved["data"]["rule"] == "plan_paid_locked"
    merged = _put(client, cid, [{**p2, "amount": p1["amount"] + p2["amount"]}, p3], why)
    assert merged["data"]["rule"] == "plan_paid_locked"  # 删掉已收齐的第一期
    below = _put(client, cid, [p1, {**p2, "amount": 1_000_000}, {**p3, "amount": 9_500_000}], why)
    assert below["data"]["rule"] == "plan_paid_locked"  # 第二期已收 ¥15,000


def test_reason_required_and_recorded(client: TestClient, tracker: Tracker) -> None:
    cid, (p1, p2, p3) = _paid_contract(client, tracker)
    items = [p1, {**p2, "due_date": "2099-06-30"}, p3]
    missing = _put(client, cid, items)
    assert missing["code"] == 42201 and missing["data"]["rule"] == "plan_reason_required"
    ok = _put(client, cid, items, "客户申请第二期延期")
    assert ok["code"] == 0 and ok["data"]["items"][1]["due_date"] == "2099-06-30"
    with session_scope() as db:
        text = db.scalar(
            select(Activity.content)
            .where(Activity.subject_id == uuid.UUID(cid), Activity.action == "payment_plan")
            .order_by(Activity.created_at.desc())
        )
    assert text and "原计划" in text and p2["due_date"] in text and "客户申请第二期延期" in text


def test_list_shows_invoice_pending_and_plan_amount(client: TestClient, tracker: Tracker) -> None:
    cid, (p1, p2, _) = _paid_contract(client, tracker)
    item = client.get(f"/api/contracts/{cid}", headers=SALES_H).json()["data"]
    assert item["invoice_pending"] >= 1  # 第一期已收齐、还没开票
    nxt = item["next_payment"]
    assert (nxt["name"], nxt["plan_amount"]) == (p2["name"], p2["amount"])
    assert nxt["amount"] == p1["amount"] + p2["amount"] - 6_000_000
