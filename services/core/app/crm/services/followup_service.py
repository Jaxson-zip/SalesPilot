"""跟进记录 service。"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.scope import ensure_visible
from app.crm.models import Customer, Followup
from app.crm.services import activity_service

FollowupType = Literal["phone", "visit", "wechat", "ai"]


class FollowupCreate(BaseModel):
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    type: FollowupType = "phone"
    content: str = Field(min_length=1, max_length=2000)


class FollowupOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    type: str
    content: str
    source: str


def add_followup(
    db: Session, user: CurrentUser, data: FollowupCreate, source: str = "manual"
) -> FollowupOut:
    customer = db.get(Customer, data.customer_id)
    ensure_visible(customer, user)
    assert customer is not None
    followup = Followup(
        **data.model_dump(), source=source, owner_id=customer.owner_id, team_id=customer.team_id
    )
    db.add(followup)
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, f"followup.{data.type}", data.content, source
    )
    return FollowupOut(
        id=followup.id,
        customer_id=followup.customer_id,
        type=followup.type,
        content=followup.content,
        source=followup.source,
    )
