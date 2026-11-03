"""一处数据变了，别处的同一份数据要跟着变（2026-11-03 审查的 6 个问题的回归用例）。

1. 退回公海：没成交的报价关闭、待审批驳回、未完成的待办完成（原来变成无人负责）
2. 成员调团队：名下客户和进行中的业务跟人走（原来留在原团队，新主管看不到）
3. 赢单：同商机的其他报价关闭（原来还停在已发送）
4. 分享链接：已关闭的报价打开不算客户在看
5. 事情处理完：对应的提醒标为已读
6. 删除联系人：还能修改的报销单用到时拒绝

都在事务里跑完回滚，不在测试库里留数据。
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import Role
from app.common.db import get_sessionmaker
from app.common.errors import BizError
from app.crm.models import (
    Approval,
    Contact,
    Contract,
    Customer,
    Expense,
    Notification,
    Opportunity,
    PaymentPlan,
    Quote,
    QuoteShare,
    Task,
    Team,
    User,
)
from app.crm.schemas.account import AccountUpdate
from app.crm.schemas.finance import PaymentIn
from app.crm.schemas.opportunity import StageChange
from app.crm.schemas.report import DailyReportIn
from app.crm.schemas.task import TaskUpdate
from app.crm.services import (
    account_service,
    approval_service,
    contact_service,
    notification_service,
    payment_service,
    pool_service,
    report_service,
    share_service,
    task_service,
)
from app.crm.services.codes import local_today
from app.crm.services.demo import DEMO_USERS
from app.crm.services.opportunity_service import apply_stage

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
ADMIN = DEMO_USERS[Role.ADMIN]


@pytest.fixture
def db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _tag() -> str:
    return uuid.uuid4().hex[:6]


def _owner(user_id: uuid.UUID, team_id: uuid.UUID | None) -> dict[str, uuid.UUID | None]:
    return {"owner_id": user_id, "team_id": team_id}


def _customer(db: Session, owner: dict[str, uuid.UUID | None]) -> Customer:
    c = Customer(name=f"同步测试客户 {_tag()}", **owner)
    db.add(c)
    db.flush()
    return c


def _quote(db: Session, c: Customer, status: str, opp: Opportunity | None = None) -> Quote:
    q = Quote(
        code=f"Q-SYNC-{_tag()}",
        customer_id=c.id,
        opportunity_id=opp.id if opp else None,
        pack="llm_deploy",
        tier="standard",
        status=status,
        owner_id=c.owner_id,
        team_id=c.team_id,
    )
    db.add(q)
    db.flush()
    return q


def _task(db: Session, c: Customer, days: int = 1) -> Task:
    t = Task(
        title=f"同步测试任务 {_tag()}",
        type="call",
        subject_type="customer",
        subject_id=c.id,
        customer_id=c.id,
        due_at=datetime.now(UTC) + timedelta(days=days),
        owner_id=c.owner_id,
        team_id=c.team_id,
    )
    db.add(t)
    db.flush()
    return t


def _pending_approval(db: Session, q: Quote) -> Approval:
    a = Approval(
        target_type="quote", target_id=q.id, reason="测试", status="pending",
        owner_id=q.owner_id, team_id=q.team_id,
    )  # fmt: skip
    db.add(a)
    db.flush()
    notification_service.notify(
        db, [MANAGER.id], "approval_pending", "待审批", None, f"/approvals?id={a.id}"
    )
    return a


def _unread(db: Session, cond: object) -> int:
    rows = db.scalars(select(Notification).where(cond, Notification.read.is_(False)))  # type: ignore[arg-type]
    return len(list(rows))


def test_release_to_pool_closes_open_quotes_and_tasks(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    sent, pending = _quote(db, c, "sent"), _quote(db, c, "pending_approval")
    accepted = _quote(db, c, "accepted")
    approval = _pending_approval(db, pending)
    task = _task(db, c)
    pool_service.release(db, SALES, c.id, "客户暂无需求")
    for q in (sent, pending, accepted, task, approval):
        db.refresh(q)
    assert (sent.status, pending.status, accepted.status) == ("closed", "closed", "accepted")
    assert approval.status == "rejected"
    assert task.done and "退回公海" in (task.note or "")
    assert _unread(db, Notification.link == f"/approvals?id={approval.id}") == 0


def test_team_change_moves_open_work(db: Session) -> None:
    team = Team(name=f"新团队 {_tag()}")
    member = User(name="调岗销售", role="sales", team_id=SALES.team_id, username=f"m{_tag()}")
    db.add_all([team, member])
    db.flush()
    c = _customer(db, _owner(member.id, SALES.team_id))
    opp = Opportunity(
        customer_id=c.id,
        name="调岗商机",
        stage="proposal",
        amount=0,
        **_owner(member.id, SALES.team_id),
    )
    db.add(opp)
    db.flush()
    q = _quote(db, c, "pending_approval", opp)
    approval = _pending_approval(db, q)
    task = _task(db, c)
    account_service.update_account(db, ADMIN, member.id, AccountUpdate(team_id=team.id))
    for row in (c, opp, q, approval, task):
        db.refresh(row)
        assert row.team_id == team.id
        assert row.owner_id == member.id


def test_win_closes_other_quotes_of_the_deal(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    opp = Opportunity(
        customer_id=c.id,
        name="赢单商机",
        stage="negotiation",
        amount=0,
        **_owner(SALES.id, SALES.team_id),
    )
    db.add(opp)
    db.flush()
    won, other = _quote(db, c, "accepted", opp), _quote(db, c, "sent", opp)
    apply_stage(db, SALES, opp, StageChange(stage="won"))
    db.refresh(won)
    db.refresh(other)
    assert (won.status, other.status) == ("accepted", "closed")


def test_closed_quote_share_is_not_counted_as_viewed(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    q = _quote(db, c, "closed")
    share = QuoteShare(
        quote_id=q.id, token=f"t{uuid.uuid4().hex}", created_by=SALES.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )  # fmt: skip
    db.add(share)
    db.flush()
    out = share_service.public_quote(db, share.token)
    db.refresh(share)
    assert out.status == "closed"  # 页面据此显示「已失效」
    assert share.view_count == 0
    assert _unread(db, Notification.link == f"/quotes/{q.id}") == 0


def test_task_reminders_cleared_when_done(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    task = _task(db, c, days=-2)
    notification_service.notify_once(
        db, SALES.id, "task_overdue", "逾期", f"task_overdue:{task.id}"
    )
    task_service.update_task(db, SALES, task.id, TaskUpdate(done=True))
    assert _unread(db, Notification.dedupe_key == f"task_overdue:{task.id}") == 0


def test_approval_reminders_cleared_when_decided(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    approval = _pending_approval(db, _quote(db, c, "pending_approval"))
    approval_service.decide(db, MANAGER, approval.id, "reject", "价格太低")
    assert _unread(db, Notification.link == f"/approvals?id={approval.id}") == 0


def test_payment_reminders_cleared_when_paid(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    contract = Contract(
        code=f"HT-SYNC-{_tag()}", customer_id=c.id, amount=50_000, paid_amount=0,
        **_owner(SALES.id, SALES.team_id),
    )  # fmt: skip
    db.add(contract)
    db.flush()
    plan = PaymentPlan(
        contract_id=contract.id, seq=1, name="全款", amount=50_000,
        due_date=local_today() - timedelta(days=3), **_owner(SALES.id, SALES.team_id),
    )  # fmt: skip
    db.add(plan)
    db.flush()
    key = f"payment_overdue:{plan.id}:{SALES.id}"
    notification_service.notify_once(db, SALES.id, "payment_overdue", "回款逾期", key)
    payment_service.add_payment(db, MANAGER, contract.id, PaymentIn(amount=50_000))
    assert _unread(db, Notification.dedupe_key == key) == 0


def test_report_reminder_cleared_when_submitted(db: Session) -> None:
    today = local_today()
    key = f"report_remind:{SALES.id}:{today.isoformat()}"
    db.execute(
        Notification.__table__.update().where(Notification.dedupe_key == key).values(read=False)
    )
    notification_service.notify_once(db, SALES.id, "report_remind", "日报", key)
    report_service.save_daily(db, SALES, DailyReportIn(date=today, content="今天", submit=False))
    assert _unread(db, Notification.dedupe_key == key) == 1  # 草稿不算提交
    report_service.save_daily(db, SALES, DailyReportIn(date=today, content="今天", submit=True))
    assert _unread(db, Notification.dedupe_key == key) == 0


def test_contact_in_open_expense_cannot_be_deleted(db: Session) -> None:
    c = _customer(db, _owner(SALES.id, SALES.team_id))
    contact = Contact(customer_id=c.id, name="王经理", **_owner(SALES.id, SALES.team_id))
    db.add(contact)
    db.flush()
    expense = Expense(
        code=f"E-SYNC-{_tag()}", type="entertainment", amount=30_000, occurred_on=local_today(),
        customer_id=c.id, contact_ids=[contact.id], status="rejected",
        **_owner(SALES.id, SALES.team_id),
    )  # fmt: skip
    db.add(expense)
    db.flush()
    with pytest.raises(BizError) as err:
        contact_service.delete_contact(db, SALES, c.id, contact.id)
    assert expense.code in err.value.message
    expense.status = "approved"  # 审批完：参与人另存了文字，可以删
    db.flush()
    contact_service.delete_contact(db, SALES, c.id, contact.id)
