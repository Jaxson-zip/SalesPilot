"""跟进记录 service：Agent 记跟进、客户详情的跟进列表与手工新建（接口契约 §8）。"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.common.scope import can_see, ensure_visible
from app.crm.models import Customer, Followup, Opportunity
from app.crm.schemas.common import Page
from app.crm.schemas.dashboard import FollowupIn, FollowupItem, FollowupType
from app.crm.schemas.fields import PastTime
from app.crm.services import activity_service


class FollowupCreate(BaseModel):
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    type: FollowupType = "phone"
    content: str = Field(min_length=1, max_length=2000)
    occurred_at: PastTime | None = None


class FollowupOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    type: str
    content: str
    source: str


def _load_customer(db: Session, user: CurrentUser, customer_id: uuid.UUID) -> Customer:
    customer = db.get(Customer, customer_id)
    ensure_visible(customer, user)
    assert customer is not None
    return customer


def _check_opportunity(
    db: Session, user: CurrentUser, customer: Customer, opportunity_id: uuid.UUID | None
) -> None:
    if opportunity_id is None:
        return
    opp = db.get(Opportunity, opportunity_id)
    if opp is None or not can_see(opp, user):
        raise BizError(ErrorCode.NOT_FOUND, "商机不存在")
    if opp.customer_id != customer.id:
        raise BizError(ErrorCode.VALIDATION, "商机不属于该客户")


def _create(db: Session, user: CurrentUser, data: FollowupCreate, source: str) -> Followup:
    """写跟进：只有客户负责人本人可以（管理员 role_forbidden，主管写销售的客户 not_owner）。"""
    customer = db.get(Customer, data.customer_id)
    ensure_owner(customer, user)
    assert customer is not None
    _check_opportunity(db, user, customer, data.opportunity_id)
    followup = Followup(
        **data.model_dump(), source=source, owner_id=customer.owner_id, team_id=customer.team_id
    )
    db.add(followup)
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, f"followup.{data.type}", data.content, source, customer
    )
    return followup


def add_followup(
    db: Session, user: CurrentUser, data: FollowupCreate, source: str = "manual"
) -> FollowupOut:
    followup = _create(db, user, data, source)
    return FollowupOut(
        id=followup.id,
        customer_id=followup.customer_id,
        type=followup.type,
        content=followup.content,
        source=followup.source,
    )


def _to_item(f: Followup) -> FollowupItem:
    return FollowupItem(
        id=f.id,
        customer_id=f.customer_id,
        opportunity_id=f.opportunity_id,
        type=f.type,
        content=f.content,
        source="agent" if f.source == "agent" else "manual",
        occurred_at=f.occurred_at or f.created_at,
        created_at=f.created_at,
    )


def create_for_customer(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, data: FollowupIn
) -> FollowupItem:
    followup = _create(
        db, user, FollowupCreate(customer_id=customer_id, **data.model_dump()), "manual"
    )
    db.refresh(followup)
    return _to_item(followup)


def list_for_customer(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, limit: int = 20
) -> Page[FollowupItem]:
    _load_customer(db, user, customer_id)
    where = Followup.customer_id == customer_id
    total = db.scalar(select(func.count()).select_from(Followup).where(where)) or 0
    stmt = (
        select(Followup)
        .where(where)
        .order_by(func.coalesce(Followup.occurred_at, Followup.created_at).desc(), Followup.id)
        .limit(limit)
    )
    return Page[FollowupItem](items=[_to_item(f) for f in db.scalars(stmt)], total=total)
