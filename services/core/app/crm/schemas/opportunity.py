"""商机 schema（接口契约 §2）。金额单位：分；win_rate 为 0–100 的整数。"""

import uuid
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.crm.schemas.common import ActivityOut, CustomerBrief, ProductLineBrief, UserBrief
from app.crm.schemas.quote import QuoteListItem

Stage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
STAGES: tuple[str, ...] = ("lead", "qualified", "proposal", "negotiation", "won", "lost")
FINAL_STAGES: frozenset[str] = frozenset({"won", "lost"})
STAGE_LABELS: dict[str, str] = {
    "lead": "线索",
    "qualified": "需求确认",
    "proposal": "方案报价",
    "negotiation": "商务谈判",
    "won": "赢单",
    "lost": "输单",
}


class OpportunityItem(BaseModel):
    id: uuid.UUID
    name: str
    customer: CustomerBrief
    stage: Stage
    amount: int
    win_rate: int
    expected_close_date: date | None
    product_line: ProductLineBrief | None
    owner: UserBrief | None
    lost_reason: str | None = None
    updated_at: datetime


class OpportunityDetail(OpportunityItem):
    quotes: list[QuoteListItem]
    activities: list[ActivityOut]


class OpportunityCreate(BaseModel):
    customer_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    amount: int = Field(ge=0)
    win_rate: int = Field(default=10, ge=0, le=100)
    expected_close_date: date | None = None
    product_line_id: uuid.UUID | None = None


class OpportunityUpdate(BaseModel):
    """只修改传入的字段。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: int | None = Field(default=None, ge=0)
    win_rate: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    product_line_id: uuid.UUID | None = None


class StageChange(BaseModel):
    stage: Stage
    lost_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _lost_needs_reason(self) -> Self:
        if self.stage == "lost" and not (self.lost_reason or "").strip():
            raise ValueError("输单时必须填写 lost_reason")
        return self


class PipelineStage(BaseModel):
    stage: str
    count: int
    amount: int


class PipelineSummary(BaseModel):
    stages: list[PipelineStage]
    total_amount: int
    weighted_amount: int
