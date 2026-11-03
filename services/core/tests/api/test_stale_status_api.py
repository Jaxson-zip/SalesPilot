"""外部复测：输单后审批建议和「这单赚多少」还停在旧状态；输单修复前留下的报价没关。"""

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

from fastapi.testclient import TestClient

from app.common.db import session_scope
from app.crm.models import Approval, Opportunity, Quote, Task
from tests.api.conftest import MANAGER_H, SALES_H, Tracker, make_tier
from tests.api.test_deal_closeout_api import _lose
from tests.api.test_expenses_approvals_api import new_expense, with_receipts
from tests.api.test_opportunities_api import new_opp
from tests.api.test_quotes_contracts_api import GOOD, LOW, act, create_quote

MIGRATION = Path(__file__).parents[2] / "migrations" / "versions" / "0030_close_lost_quotes.py"


def _approval_of(client: TestClient, target_id: str) -> dict:
    url = "/api/approvals?status=pending&page_size=100"
    items = client.get(url, headers=MANAGER_H).json()["data"]["items"]
    return next(a for a in items if a["target"]["id"] == target_id)


def test_approval_shows_current_deal_state(client: TestClient, tracker: Tracker) -> None:
    """回归：商机已输单，报销审批仍写着「处于方案报价阶段，超标幅度可接受」。"""
    opp = new_opp(client, tracker)
    eid = new_expense(client, tracker, amount=86_000, opportunity_id=opp["id"])["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    before = _approval_of(client, eid)
    assert before["ai_suggestion"] and "当前处于线索阶段" in before["deal_note"]

    assert _lose(client, opp["id"])["code"] == 0
    after = _approval_of(client, eid)
    assert after["ai_suggestion"] == before["ai_suggestion"]  # 提交时的建议原样保留
    assert "输单" in after["deal_note"] and "提交时" in after["deal_note"]


def test_lost_deal_profit_counts_only_spent(client: TestClient, tracker: Tracker) -> None:
    """回归：输单、赢率 0% 的商机仍按报价显示「实际赚」。"""
    opp = new_opp(client, tracker)
    create_quote(tracker, make_tier(GOOD), opp["id"])
    eid = new_expense(client, tracker, amount=20_000, opportunity_id=opp["id"])["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    url = f"/api/opportunities/{opp['id']}"
    assert client.get(url, headers=SALES_H).json()["data"]["profit"]["basis"] == "latest"

    _lose(client, opp["id"])
    profit = client.get(url, headers=SALES_H).json()["data"]["profit"]
    assert profit["basis"] == "lost"
    assert profit["gross"] == 0 and profit["commission"] == 0
    assert profit["expenses"] == 20_000 and profit["net"] == -20_000


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("m0030", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_closes_quotes_of_old_lost_deals(client: TestClient, tracker: Tracker) -> None:
    """回归：输单自动关报价上线前输掉的商机，报价还是「已审批」，发送入口看得见点不了。"""
    opp = new_opp(client, tracker)
    approved = create_quote(tracker, make_tier(GOOD), opp["id"])
    act(client, approved, "submit")
    pending = create_quote(tracker, make_tier(LOW), opp["id"])
    act(client, pending, "submit")
    task = {"title": "回访", "due_at": "2026-12-01T10:00:00+08:00"}
    task |= {"subject_type": "opportunity", "subject_id": opp["id"]}
    client.post("/api/tasks", json=task, headers=SALES_H)
    oid = uuid.UUID(opp["id"])
    with session_scope() as db:  # 模拟修复前的输单：只改阶段，不收尾
        db.get(Opportunity, oid).stage = "lost"  # type: ignore[union-attr]

    with session_scope() as db:
        for stmt in _migration().STATEMENTS:
            db.execute(stmt)
    with session_scope() as db:
        ids = [uuid.UUID(approved), uuid.UUID(pending)]
        assert {db.get(Quote, i).status for i in ids} == {"closed"}  # type: ignore[union-attr]
        a = db.query(Approval).filter(Approval.target_id == ids[1]).one()
        assert a.status == "rejected" and a.comment == "商机已输单，自动关闭"
        t = db.query(Task).filter(Task.subject_id == oid).one()
        assert t.done and t.note == "商机已输单，自动关闭"
