"""报价单 schema。"""

import uuid
from typing import Literal

from pydantic import BaseModel

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
