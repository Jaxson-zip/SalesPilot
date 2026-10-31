"""报价单 schema（接口契约 §3）。金额单位：分。"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.crm.schemas.common import CustomerBrief, OppBrief, UserBrief
from app.crm.schemas.fields import ItemName
from app.packs.base import Category, ClientCost

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


EXTRA_PREFIX = "extra-"


class QuoteLineIn(BaseModel):
    """一行明细。目录物料传 sku + 数量，可以带 unit_price 改单价（不带沿用原价）；
    自己加的费用（sku 以 extra- 开头，如加急费、差旅费、第三方服务）还要传名称和单价，
    成本不填按 0 算。"""

    sku: str = Field(min_length=1, max_length=50)
    qty: int = Field(ge=1, le=100_000)
    name: ItemName | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    unit_price: int | None = Field(default=None, ge=0, le=10_000_000_000)
    unit_cost: int | None = Field(default=None, ge=0, le=10_000_000_000)
    category: Category | None = None

    @property
    def is_extra(self) -> bool:
        return self.sku.startswith(EXTRA_PREFIX)


class QuoteCreate(BaseModel):
    """不经过 AI，自己从零出一张报价（草稿）。商机和客户至少填一个；填了商机就用商机的客户。"""

    opportunity_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    pack: str = Field(min_length=1, max_length=50)
    items: list[QuoteLineIn] = Field(min_length=1, max_length=100)
    discount_rate: float = Field(default=0, ge=0, lt=1)


class QuoteItemsUpdate(BaseModel):
    """调整后的完整明细（未列出的物料行会被移除）+ 整单折扣率。"""

    items: list[QuoteLineIn] = Field(min_length=1, max_length=100)
    discount_rate: float = Field(default=0, ge=0, lt=1)
