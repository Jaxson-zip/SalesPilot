"""合同、提成、报销、审批 schema。TODO: 按接口契约补全。"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ExpenseStatus = Literal["draft", "submitted", "pending_approval", "approved", "paid", "rejected"]


class ExpenseCreate(BaseModel):
    type: str = Field(min_length=1, max_length=30)
    amount: int = Field(gt=0)
    headcount: int = Field(default=1, ge=1, le=1000)
    participants: str | None = None
    occurred_on: date
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


class CommissionLineIn(BaseModel):
    category: Literal["hardware", "software", "service"]
    amount: int = Field(ge=0)


class CommissionEstimateIn(BaseModel):
    lines: list[CommissionLineIn]
    margin_rate: float = Field(ge=-1, le=1)
    paid_ratio: float = Field(default=1.0, ge=0, le=1)


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)
