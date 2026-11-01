"""工作台、行业包配置、客户补充（跟进 / 联系人）schema（接口契约 §1、§7、§8）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.crm.schemas.fields import ContactName, Phone, PhoneOrMasked
from app.crm.schemas.opportunity import PipelineStage

FollowupType = Literal["phone", "visit", "wechat", "email", "ai"]  # ai = Agent 记录


class Dashboard(BaseModel):
    won_amount_month: int
    open_opportunities: int
    open_amount: int
    pending_approvals: int
    # 待审批按类型分开（报价 / 报销）：工作台卡片点进对应列表
    pending_quotes: int = 0
    pending_expenses: int = 0
    estimated_commission_month: int
    confirmed_commission_month: int
    tasks_today: int = 0  # v3 §12：今天到期的未完成任务
    tasks_overdue: int = 0  # v3 §12：已逾期的任务
    target_month: int | None = None  # 当前范围内本月业绩目标之和；没人设目标为 null
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
    type: FollowupType
    content: str
    source: Literal["manual", "agent"]
    occurred_at: datetime
    created_at: datetime


# 联系人在采购决策中的角色（Salesforce 的 Contact Role）
ContactRole = Literal["decision_maker", "influencer", "technical", "finance", "user"]
CONTACT_ROLE_LABELS: dict[str, str] = {
    "decision_maker": "决策人",
    "influencer": "影响者",
    "technical": "技术把关",
    "finance": "采购 / 财务",
    "user": "使用者",
}


class ContactItem(BaseModel):
    id: uuid.UUID
    name: str
    title: str | None
    phone: str | None  # 脱敏后的号码（139****2222）；完整号码走 POST .../phone，记入操作日志
    has_phone: bool = False
    is_decision_maker: bool
    role: ContactRole | None


class PhoneOut(BaseModel):
    phone: str
    remaining: int  # 今天还能查看的次数


class ContactIn(BaseModel):
    name: ContactName
    title: str | None = Field(default=None, max_length=50)
    phone: Phone = None
    role: ContactRole | None = None


class ContactUpdate(BaseModel):
    name: ContactName | None = None
    title: str | None = Field(default=None, max_length=50)
    phone: PhoneOrMasked = None
    role: ContactRole | None = None
