"""工作台、行业包配置、客户补充（跟进 / 联系人）schema（接口契约 §1、§7、§8）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.crm.schemas.opportunity import PipelineStage


class Dashboard(BaseModel):
    won_amount_month: int
    open_opportunities: int
    open_amount: int
    pending_approvals: int
    estimated_commission_month: int
    confirmed_commission_month: int
    tasks_today: int = 0  # v3 §12：今天到期的未完成任务
    tasks_overdue: int = 0  # v3 §12：已逾期的任务
    funnel: list[PipelineStage]


class ProductLineItem(BaseModel):
    id: uuid.UUID
    name: str
    pack: str
    enabled: bool
    open_opportunities: int


class ProductLineUpdate(BaseModel):
    pack: str | None = Field(default=None, min_length=1, max_length=50)
    enabled: bool | None = None


class FollowupIn(BaseModel):
    type: Literal["phone", "visit", "wechat", "email"]
    content: str = Field(min_length=1, max_length=2000)
    occurred_at: datetime | None = None
    opportunity_id: uuid.UUID | None = None


class FollowupItem(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None
    type: str
    content: str
    source: Literal["manual", "agent"]
    occurred_at: datetime
    created_at: datetime


class ContactItem(BaseModel):
    id: uuid.UUID
    name: str
    title: str | None
    phone: str | None
    is_decision_maker: bool
