"""工作台待办里除任务以外的事项：回款逾期 / 今天到期、今天的日报、主管的待审批。

回归：原来待办只读任务表，回款逾期和日报催交只发通知，待办里看不到。
service 用例在事务里跑完回滚，不在测试库里留数据。
"""

import uuid
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.auth import Role
from app.common.db import get_sessionmaker
from app.crm.models import Contract, Customer, DailyReport, PaymentPlan
from app.crm.services import approval_service, todo_service
from app.crm.services.codes import local_today
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES
from tests.api.conftest import SALES_H

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
MONDAY = date(2026, 11, 2)


@pytest.fixture
def db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _contract(db: Session, owner_id: uuid.UUID, team_id: uuid.UUID | None) -> Contract:
    owner = {"owner_id": owner_id, "team_id": team_id}
    c = Customer(name=f"待办测试客户 {uuid.uuid4().hex[:6]}", **owner)
    db.add(c)
    db.flush()
    contract = Contract(
        code=f"HT-TODO-{uuid.uuid4().hex[:6]}",
        customer_id=c.id,
        amount=100_000,
        paid_amount=10_000,
        **owner,
    )
    db.add(contract)
    db.flush()
    today = local_today()
    plans = [
        ("预付款", 30_000, today - timedelta(days=5)),
        ("验收款", 30_000, today),
        ("尾款", 40_000, today + timedelta(days=30)),
    ]
    for seq, (name, amount, due) in enumerate(plans, start=1):
        db.add(
            PaymentPlan(
                contract_id=contract.id, seq=seq, name=name, amount=amount, due_date=due, **owner
            )
        )
    db.flush()
    return contract


def test_overdue_and_due_today_payments_are_todos(db: Session) -> None:
    contract = _contract(db, SALES.id, SALES.team_id)
    other = _contract(db, EXTRA_SALES.id, EXTRA_SALES.team_id)
    items = todo_service.list_todos(db, SALES)
    mine = [t for t in items if contract.code in t.title]
    kinds = [(t.kind, t.overdue) for t in mine]
    assert kinds == [("payment_overdue", True), ("payment_due", False)]
    assert mine[0].title == f"催回款：{contract.code} 预付款"
    assert mine[0].detail == "应收 ¥200.00，已逾期 5 天"  # 300 元的预付款已回 100
    assert mine[1].detail == "应收 ¥300.00，今天到期"
    assert mine[0].link == f"/contracts?plan={contract.id}"
    # 别人的合同不出现；未来到期的尾款不算
    assert not [t for t in items if other.code in t.title]
    assert not [t for t in items if "尾款" in t.title and contract.code in t.title]


def test_paid_off_payment_leaves_todos(db: Session) -> None:
    contract = _contract(db, SALES.id, SALES.team_id)
    contract.paid_amount = 60_000  # 预付款、验收款都收齐
    db.flush()
    assert not [t for t in todo_service.list_todos(db, SALES) if contract.code in t.title]


def test_report_todo_until_submitted(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(todo_service, "local_today", lambda: MONDAY)
    db.query(DailyReport).filter(
        DailyReport.user_id == SALES.id, DailyReport.report_date == MONDAY
    ).delete()
    item = todo_service.report_item(db, SALES, None)
    assert item is not None and item.link == "/reports"
    db.add(DailyReport(user_id=SALES.id, report_date=MONDAY, content="今天", status="draft"))
    db.flush()
    assert todo_service.report_item(db, SALES, None) is not None  # 草稿不算提交
    db.query(DailyReport).filter(DailyReport.user_id == SALES.id).update({"status": "submitted"})
    assert todo_service.report_item(db, SALES, None) is None
    # 主管不写日报，周末不催
    assert todo_service.report_item(db, MANAGER, None) is None
    monkeypatch.setattr(todo_service, "local_today", lambda: MONDAY - timedelta(days=1))
    db.query(DailyReport).filter(DailyReport.user_id == SALES.id).delete()
    assert todo_service.report_item(db, SALES, None) is None


def test_manager_sees_pending_approvals(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    counts = {"quote": 2, "expense": 1}
    monkeypatch.setattr(approval_service, "count_pending_by_type", lambda *_a: counts)
    item = todo_service.approval_item(db, MANAGER)
    assert item is not None
    assert item.title == "处理待审批（3 条）"
    assert (item.detail, item.link) == ("报价 2 条、报销 1 条", "/approvals")
    assert todo_service.approval_item(db, SALES) is None
    counts.update(quote=0, expense=0)
    assert todo_service.approval_item(db, MANAGER) is None


def test_todos_api(client: TestClient) -> None:
    r = client.get("/api/dashboard/todos", headers=SALES_H)
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert all({"kind", "title", "link"} <= set(t) for t in body["data"])


def test_todos_api_requires_login(client: TestClient) -> None:
    r = client.get("/api/dashboard/todos")
    assert r.json()["code"] == 40101
