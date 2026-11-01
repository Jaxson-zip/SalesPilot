"""商机 schema（接口契约 §2）。金额单位：分；win_rate 为 0–100 的整数。"""

import uuid
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.crm.schemas.common import ActivityOut, CustomerBrief, ProductLineBrief, UserBrief
from app.crm.schemas.fields import Amount, OpportunityName, PlanDate
from app.crm.schemas.quote import QuoteListItem
from app.crm.schemas.task import NextTask

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
    # v3 §12 / §13：下一步行动与停滞提醒
    next_task: NextTask | None = None
    last_activity_at: datetime | None = None
    idle_days: int = 0
    stale: bool = False
    # 看板卡片：当前阶段应确认却没确认的赢单要素、标注的竞品名称
    meddic_risks: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)


class OpportunityExpenses(BaseModel):
    """这单的跟单费用（报销关联到商机的），单位分。"""

    approved: int = 0  # 已批准 + 已付款
    pending: int = 0  # 审批中
    count: int = 0  # 不含草稿和被驳回的


class OpportunityProfit(BaseModel):
    """这单实际赚多少（分）：报价毛利 − 预估提成 − 跟单费用（已批 + 审批中）。"""

    quote_id: uuid.UUID
    quote_code: str
    # accepted：按客户已接受的报价；latest：还没成交，按最新一张有效报价估算
    basis: Literal["accepted", "latest"]
    price: int
    gross: int
    commission: int
    expenses: int
    net: int


class OpportunityDetail(OpportunityItem):
    quotes: list[QuoteListItem]
    activities: list[ActivityOut]
    expenses: OpportunityExpenses = Field(default_factory=OpportunityExpenses)
    profit: OpportunityProfit | None = None


class OpportunityCreate(BaseModel):
    customer_id: uuid.UUID
    name: OpportunityName
    amount: Amount
    win_rate: int = Field(default=10, ge=0, le=100)
    expected_close_date: PlanDate | None = None
    product_line_id: uuid.UUID | None = None


class OpportunityUpdate(BaseModel):
    """只修改传入的字段。"""

    name: OpportunityName | None = None
    amount: Amount | None = None
    win_rate: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: PlanDate | None = None
    product_line_id: uuid.UUID | None = None


class StageChange(BaseModel):
    stage: Stage
    lost_reason: str | None = Field(default=None, max_length=500)
    # 赢单时按这张报价单成交：生成合同、回款计划和提成（与报价单「客户接受」相同）
    quote_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _lost_needs_reason(self) -> Self:
        if self.stage == "lost" and not (self.lost_reason or "").strip():
            raise ValueError("输单时必须填写 lost_reason")
        if self.quote_id is not None and self.stage != "won":
            raise ValueError("只有赢单时才能指定 quote_id")
        return self


class PipelineStage(BaseModel):
    stage: Stage
    count: int
    amount: int
    # 只有赢单阶段有值：其中还没有合同的商机（手工标赢单），不计入「本月成交」
    unsigned_count: int = 0
    unsigned_amount: int = 0


class PipelineSummary(BaseModel):
    stages: list[PipelineStage]
    total_amount: int  # 进行中商机金额合计（不含赢单、输单）
    weighted_amount: int
    open_count: int
