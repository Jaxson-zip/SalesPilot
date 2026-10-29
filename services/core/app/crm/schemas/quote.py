"""报价单 schema（接口契约 §3）。金额单位：分。"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.crm.schemas.common import CustomerBrief, OppBrief, UserBrief
from app.packs.base import ClientCost

QuoteStatus = Literal["draft", "pending_approval", "approved", "sent", "accepted", "rejected"]

QUOTE_STATUS_LABELS: dict[str, str] = {
    "draft": "草稿",
    "pending_approval": "待主管审批",
    "approved": "已审批",
    "sent": "已发送客户",
    "accepted": "已成交",
    "rejected": "已驳回",
}


class QuoteItemOut(BaseModel):
    sku: str
    name: str
    unit: str
    qty: int
    unit_cost: int
    unit_price: int
    category: str


class QuoteOut(BaseModel):
    """Agent generate_quote 的返回（对话里的报价卡片）。"""

    id: uuid.UUID
    code: str
    opportunity_id: uuid.UUID | None
    pack: str
    tier: str
    status: QuoteStatus
    total_cost: int
    total_price: int
    margin_rate: float
    items: list[QuoteItemOut] = []
    client_costs: list[ClientCost] = []


class QuoteLine(QuoteItemOut):
    subtotal_cost: int
    subtotal_price: int


class ApprovalBrief(BaseModel):
    id: uuid.UUID
    status: Literal["pending", "approved", "rejected"]
    reason: str
    approver: UserBrief | None
    comment: str | None
    decided_at: datetime | None


class QuoteListItem(BaseModel):
    id: uuid.UUID
    code: str
    customer: CustomerBrief | None
    opportunity: OppBrief | None
    pack: str
    tier: str
    tier_name: str
    total_price: int
    total_cost: int
    margin_rate: float
    status: QuoteStatus
    source: Literal["agent", "manual"]
    owner: UserBrief | None
    created_at: datetime


class QuoteDetail(QuoteListItem):
    items: list[QuoteLine]
    approvals: list[ApprovalBrief]
    contract_id: uuid.UUID | None
    estimated_commission: int
    # v3 §14
    list_price: int  # 折前合计 = Σ 单价 × 数量
    discount_rate: float
    valid_until: date
    # 运营期客户自付费用（实报实销，不含在报价内）
    client_costs: list[ClientCost] = []


class QuoteLineIn(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    qty: int = Field(ge=1, le=100_000)


class QuoteItemsUpdate(BaseModel):
    """调整后的完整明细（未列出的物料行会被移除）+ 整单折扣率。"""

    items: list[QuoteLineIn] = Field(min_length=1, max_length=100)
    discount_rate: float = Field(default=0, ge=0, lt=1)
