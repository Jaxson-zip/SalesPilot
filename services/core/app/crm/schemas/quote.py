"""报价单 schema。"""

import uuid
from typing import Literal

from pydantic import BaseModel

QuoteStatus = Literal["draft", "pending_approval", "approved", "sent", "accepted", "rejected"]


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
