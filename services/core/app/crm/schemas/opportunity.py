"""商机 schema。TODO: 列表 / 详情 / 新建 / 看板接口的完整字段。"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
STAGES: tuple[str, ...] = ("lead", "qualified", "proposal", "negotiation", "won", "lost")


class OpportunityOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    stage: Stage
    amount: int
    win_rate: int
    expected_close_date: date | None
    product_line_id: uuid.UUID | None


class OpportunityCreate(BaseModel):
    customer_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    amount: int = Field(default=0, ge=0)
    product_line_id: uuid.UUID
    expected_close_date: date | None = None


class StageChange(BaseModel):
    stage: Stage


class PipelineStage(BaseModel):
    stage: str
    count: int
    amount: int
