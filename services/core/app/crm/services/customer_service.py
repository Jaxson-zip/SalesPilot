"""客户 service（参考实现）：业务逻辑、数据范围过滤都在这里，router 只做参数和响应。"""

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.scope import View, apply_scope, ensure_visible
from app.crm.models import Customer, Followup, Opportunity, User
from app.crm.schemas.common import Page, PageParams, UserBrief
from app.crm.schemas.customer import (
    CustomerBrief,
    CustomerCreate,
    CustomerDetail,
    CustomerListItem,
)
from app.crm.services import activity_service


def _opportunity_amount_subq() -> Any:
    return (
        select(Opportunity.customer_id, func.sum(Opportunity.amount).label("amount"))
        .where(Opportunity.stage != "lost")
        .group_by(Opportunity.customer_id)
        .subquery("opp")
    )


def _last_followup_subq() -> Any:
    return (
        select(Followup.customer_id, func.max(Followup.created_at).label("last_at"))
        .group_by(Followup.customer_id)
        .subquery("fu")
    )


def build_list_query(user: CurrentUser, view: View | None, q: str | None) -> Select[Any]:
    """列表查询（不含分页）：客户 + 负责人 + 商机金额合计 + 最近跟进时间，按数据范围过滤。"""
    opp = _opportunity_amount_subq()
    fu = _last_followup_subq()
    stmt = (
        select(
            Customer,
            User.name.label("owner_name"),
            func.coalesce(opp.c.amount, 0).label("opportunity_amount"),
            fu.c.last_at.label("last_followup_at"),
        )
        .outerjoin(User, User.id == Customer.owner_id)
        .outerjoin(opp, opp.c.customer_id == Customer.id)
        .outerjoin(fu, fu.c.customer_id == Customer.id)
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.industry.ilike(pattern)))
    return apply_scope(stmt, Customer, user, view)


def _owner(customer: Customer, owner_name: str | None) -> UserBrief | None:
    if customer.owner_id is None or owner_name is None:
        return None
    return UserBrief(id=customer.owner_id, name=owner_name)


def _to_item(row: Any) -> CustomerListItem:
    c: Customer = row.Customer
    return CustomerListItem(
        id=c.id,
        name=c.name,
        industry=c.industry,
        level=c.level,
        owner=_owner(c, row.owner_name),
        website=c.website,
        opportunity_amount=int(row.opportunity_amount or 0),
        last_followup_at=row.last_followup_at,
    )


def _to_detail(row: Any) -> CustomerDetail:
    c: Customer = row.Customer
    return CustomerDetail(
        **_to_item(row).model_dump(),
        size=c.size,
        address=c.address,
        annual_budget=c.annual_budget,
        tags=list(c.tags or []),
        created_at=c.created_at,
    )


def list_customers(
    db: Session, user: CurrentUser, view: View | None, q: str | None, page: PageParams
) -> Page[CustomerListItem]:
    base = build_list_query(user, view, q)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    stmt = base.order_by(Customer.created_at.desc()).offset(page.offset).limit(page.page_size)
    rows = db.execute(stmt).all()
    return Page[CustomerListItem](items=[_to_item(r) for r in rows], total=total)


def get_customer(db: Session, user: CurrentUser, customer_id: uuid.UUID) -> CustomerDetail:
    stmt = build_list_query(user, View.ALL, None).where(Customer.id == customer_id)
    row = db.execute(stmt).first()
    if row is None:
        raise BizError(ErrorCode.NOT_FOUND, "客户不存在")
    ensure_visible(row.Customer, user)
    return _to_detail(row)


def create_customer(db: Session, user: CurrentUser, data: CustomerCreate) -> CustomerDetail:
    exists = db.scalar(select(func.count()).where(Customer.name == data.name.strip()))
    if exists:
        raise BizError(ErrorCode.DUPLICATE, "客户名称已存在")
    customer = Customer(**data.model_dump(), owner_id=user.id, team_id=user.team_id)
    customer.name = data.name.strip()
    db.add(customer)
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, "create", f"创建了客户 {customer.name}"
    )
    return get_customer(db, user, customer.id)


def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


def rank_by_similarity(keyword: str, names: list[str], min_overlap: int = 2) -> list[str]:
    """按二元字组重合数排序（「明理律所」能匹配「深圳明理律师事务所」）。"""
    grams = _bigrams(keyword)
    scored = [(len(grams & _bigrams(n)), n) for n in names]
    return [n for score, n in sorted(scored, key=lambda x: -x[0]) if score >= min_overlap]


def _brief(row: Any) -> CustomerBrief:
    c: Customer = row.Customer
    return CustomerBrief(id=c.id, name=c.name, industry=c.industry, owner=_owner(c, row.owner_name))


def search_customers(
    db: Session, user: CurrentUser, keyword: str, limit: int = 5
) -> list[CustomerBrief]:
    """Agent 用：在当前用户可见范围内模糊匹配客户；子串匹配不到时按字组相似度匹配。"""
    rows = db.execute(build_list_query(user, None, keyword).limit(limit)).all()
    if rows:
        return [_brief(r) for r in rows]
    candidates = db.execute(build_list_query(user, None, None).limit(500)).all()
    by_name = {r.Customer.name: r for r in candidates}
    ranked = rank_by_similarity(keyword, list(by_name))[:limit]
    return [_brief(by_name[name]) for name in ranked]
