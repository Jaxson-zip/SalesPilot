"""业务接口测试公共夹具：需要已迁移并导入演示数据的 Postgres，连不上时 skip。

每个用例自己创建数据（商机 / 报价 / 报销），并通过 Tracker 在结束时按 id 精确清理，
不依赖执行顺序，也不改动演示数据。
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from sqlalchemy import delete, inspect, select, update
from sqlalchemy.orm import Session

from app.common import storage
from app.common.auth import CurrentUser, Role, issue_token
from app.common.db import get_engine, session_scope
from app.crm.models import (
    Activity,
    AgentThread,
    Approval,
    Attachment,
    Commission,
    Contact,
    Contract,
    Customer,
    Expense,
    Followup,
    Notification,
    Opportunity,
    Payment,
    PaymentPlan,
    Quote,
    QuoteItem,
    QuoteShare,
    Task,
)
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES
from app.packs.base import BomItem, SolutionTier
from seed.business_data import Q_HNZZ
from seed.data import C_MINGLI


def token_header(user: CurrentUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user)}"}


SALES_H = token_header(DEMO_USERS[Role.SALES])
SALES2_H = token_header(EXTRA_SALES)  # 同组另一名销售王磊
MANAGER_H = token_header(DEMO_USERS[Role.MANAGER])
ADMIN_H = token_header(DEMO_USERS[Role.ADMIN])


@pytest.fixture(autouse=True)
def require_business_db(db_available: bool) -> None:
    if not db_available:
        pytest.skip("DATABASE_URL 连不上，跳过需要数据库的用例")
    if not inspect(get_engine()).has_table("approvals"):
        pytest.skip("数据库未迁移（先执行 alembic upgrade head && python -m seed）")
    with session_scope() as db:
        if db.get(Customer, C_MINGLI) is None or db.get(Quote, Q_HNZZ) is None:
            pytest.skip("缺少演示数据（先执行 python -m seed）")


@dataclass
class Tracker:
    opportunities: list[uuid.UUID] = field(default_factory=list)
    quotes: list[uuid.UUID] = field(default_factory=list)
    expenses: list[uuid.UUID] = field(default_factory=list)
    followups: list[uuid.UUID] = field(default_factory=list)
    tasks: list[uuid.UUID] = field(default_factory=list)
    customers: list[uuid.UUID] = field(default_factory=list)

    def purge(self) -> None:
        with session_scope() as db:
            if self.customers:
                self.opportunities += list(
                    db.scalars(
                        select(Opportunity.id).where(Opportunity.customer_id.in_(self.customers))
                    )
                )
            db.execute(
                delete(Task).where(
                    Task.id.in_(self.tasks)
                    | Task.subject_id.in_(self.opportunities)
                    | Task.customer_id.in_(self.customers)
                )
            )
            _purge_expenses(db, self.expenses)
            _purge_quotes(db, self.quotes)
            _purge_quotes(
                db,
                list(
                    db.scalars(select(Quote.id).where(Quote.opportunity_id.in_(self.opportunities)))
                ),
            )
            _purge_followups(db, self.followups)
            db.execute(delete(Activity).where(Activity.subject_id.in_(self.opportunities)))
            # 从商机出方案时会话记录关联了商机
            db.execute(
                delete(AgentThread).where(AgentThread.opportunity_id.in_(self.opportunities))
            )
            db.execute(delete(Opportunity).where(Opportunity.id.in_(self.opportunities)))
            _purge_customers(db, self.customers)


def _purge_customers(db: Session, ids: list[uuid.UUID]) -> None:
    if not ids:
        return
    db.execute(delete(Activity).where(Activity.subject_id.in_(ids)))
    db.execute(delete(Followup).where(Followup.customer_id.in_(ids)))
    db.execute(delete(Contact).where(Contact.customer_id.in_(ids)))
    db.execute(delete(Customer).where(Customer.id.in_(ids)))


def _purge_followups(db: Session, ids: list[uuid.UUID]) -> None:
    """跟进的动态挂在客户上：按客户 + 内容精确删除。"""
    for f in db.scalars(select(Followup).where(Followup.id.in_(ids))).all():
        db.execute(
            delete(Activity).where(
                Activity.subject_id == f.customer_id, Activity.content == f.content
            )
        )
        db.delete(f)


def _purge_quotes(db: Session, ids: list[uuid.UUID]) -> None:
    if not ids:
        return
    contracts = list(db.scalars(select(Contract.id).where(Contract.quote_id.in_(ids))))
    db.execute(delete(Commission).where(Commission.contract_id.in_(contracts)))
    db.execute(delete(PaymentPlan).where(PaymentPlan.contract_id.in_(contracts)))
    db.execute(update(Payment).where(Payment.contract_id.in_(contracts)).values(reversal_of=None))
    db.execute(delete(Payment).where(Payment.contract_id.in_(contracts)))
    db.execute(delete(Activity).where(Activity.subject_id.in_([*ids, *contracts])))
    db.execute(delete(Contract).where(Contract.id.in_(contracts)))
    db.execute(delete(Approval).where(Approval.target_id.in_(ids)))
    db.execute(delete(QuoteItem).where(QuoteItem.quote_id.in_(ids)))
    db.execute(delete(QuoteShare).where(QuoteShare.quote_id.in_(ids)))
    db.execute(delete(Notification).where(Notification.link.in_([f"/quotes/{i}" for i in ids])))
    db.execute(delete(Quote).where(Quote.id.in_(ids)))


def _purge_expenses(db: Session, ids: list[uuid.UUID]) -> None:
    if not ids:
        return
    attachments = list(db.scalars(select(Attachment).where(Attachment.owner_ref_id.in_(ids))))
    for a in attachments:
        storage.remove(a.storage_key)
        db.delete(a)
    db.execute(delete(Approval).where(Approval.target_id.in_(ids)))
    db.execute(delete(Activity).where(Activity.subject_id.in_(ids)))
    db.execute(delete(Expense).where(Expense.id.in_(ids)))


@pytest.fixture
def tracker() -> Iterator[Tracker]:
    t = Tracker()
    yield t
    t.purge()


def make_tier(
    lines: list[tuple[str, int, int, int]], total_price: int | None = None
) -> SolutionTier:
    """lines: (category, qty, unit_cost, unit_price)。"""
    items = [
        BomItem(
            sku=f"T-{i}",
            name=f"测试物料{i}",
            category=cat,
            unit="项",
            qty=q,
            unit_cost=c,
            unit_price=p,
        )  # type: ignore[arg-type]
        for i, (cat, q, c, p) in enumerate(lines)
    ]
    price = total_price if total_price is not None else sum(i.total_price for i in items)
    return SolutionTier(
        tier="standard", name="标准版", summary="测试", items=items, total_price=price
    )
