"""报价单的查询与组装（列表项 / 明细行 / 审批记录），供 quote_service 与 opportunity_service 共用。

本模块不依赖其他 service，避免循环导入。
"""

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.scope import View, apply_scope
from app.crm.models import Approval, Customer, Quote, QuoteItem
from app.crm.schemas.quote import ApprovalBrief, QuoteLine, QuoteListItem
from app.crm.services import lookup
from app.packs.base import TIER_NAMES


def build_query(
    user: CurrentUser,
    view: View | None,
    status: str | None = None,
    opportunity_id: uuid.UUID | None = None,
    q: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> Select[Any]:
    stmt = select(Quote).outerjoin(Customer, Customer.id == Quote.customer_id)
    if status:
        stmt = stmt.where(Quote.status == status)
    if opportunity_id:
        stmt = stmt.where(Quote.opportunity_id == opportunity_id)
    if customer_id:
        stmt = stmt.where(Quote.customer_id == customer_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Quote.code.ilike(pattern), Customer.name.ilike(pattern)))
    return apply_scope(stmt, Quote, user, view)


def count(db: Session, stmt: Select[Any]) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def to_items(db: Session, quotes: list[Quote]) -> list[QuoteListItem]:
    owners = lookup.users(db, (x.owner_id for x in quotes))
    customers = lookup.customers(db, (x.customer_id for x in quotes))
    opps = lookup.opportunities(db, (x.opportunity_id for x in quotes))
    return [
        QuoteListItem(
            id=x.id,
            code=x.code,
            customer=lookup.pick(customers, x.customer_id),
            opportunity=lookup.pick(opps, x.opportunity_id),
            pack=x.pack,
            tier=x.tier,
            tier_name=TIER_NAMES.get(x.tier, x.tier),
            total_price=x.total_price,
            total_cost=x.total_cost,
            margin_rate=x.margin_rate,
            status=x.status,  # type: ignore[arg-type]
            source="agent" if x.source == "agent" else "manual",
            owner=lookup.pick(owners, x.owner_id),
            created_at=x.created_at,
        )
        for x in quotes
    ]


def list_for_opportunity(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID
) -> list[QuoteListItem]:
    stmt = build_query(user, View.ALL, opportunity_id=opportunity_id)
    quotes = list(db.scalars(stmt.order_by(Quote.created_at.desc())).all())
    return to_items(db, quotes)


def items_of(db: Session, quote_id: uuid.UUID) -> list[QuoteItem]:
    stmt = select(QuoteItem).where(QuoteItem.quote_id == quote_id).order_by(QuoteItem.created_at)
    return list(db.scalars(stmt).all())


def to_lines(items: list[QuoteItem]) -> list[QuoteLine]:
    return [
        QuoteLine(
            sku=i.sku,
            name=i.name,
            unit=i.unit,
            qty=i.qty,
            unit_cost=i.unit_cost,
            unit_price=i.unit_price,
            category=i.category,
            subtotal_cost=i.unit_cost * i.qty,
            subtotal_price=i.unit_price * i.qty,
        )
        for i in items
    ]


def approvals_of(db: Session, target_type: str, target_id: uuid.UUID) -> list[ApprovalBrief]:
    stmt = (
        select(Approval)
        .where(Approval.target_type == target_type, Approval.target_id == target_id)
        .order_by(Approval.created_at)
    )
    rows = list(db.scalars(stmt).all())
    approvers = lookup.users(db, (a.approver_id for a in rows))
    return [
        ApprovalBrief(
            id=a.id,
            status=a.status,  # type: ignore[arg-type]
            reason=a.reason,
            approver=lookup.pick(approvers, a.approver_id),
            comment=a.comment,
            decided_at=a.decided_at,
        )
        for a in rows
    ]
