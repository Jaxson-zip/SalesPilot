"""CRM 类工具（开发规范 §6.2）：都是 service 的薄包装。"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.schemas.finance import CommissionEstimateIn, CommissionLineIn, ExpenseCreate
from app.crm.services import customer_service, finance_service, followup_service
from app.crm.services import opportunity_service as opp_service
from app.crm.services.followup_service import FollowupCreate


class SearchCustomerArgs(BaseModel):
    keyword: str = Field(min_length=1, max_length=200, description="客户名称关键字")


def search_customer(ctx: ToolContext, args: SearchCustomerArgs) -> ToolResult:
    with ctx.session() as db:
        found = customer_service.search_customers(db, ctx.user, args.keyword)
    data = [c.model_dump(mode="json") for c in found]
    if not found:
        return ToolResult(ok=True, summary="没有匹配的客户", data=data)
    if len(found) > 1:
        return ToolResult(ok=True, summary=f"匹配到 {len(found)} 个客户，请确认", data=data)
    return ToolResult(ok=True, summary=found[0].name, data=data)


class AddFollowupArgs(BaseModel):
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    type: Literal["phone", "visit", "wechat", "ai"] = "phone"
    content: str = Field(min_length=1, max_length=2000)


def add_followup(ctx: ToolContext, args: AddFollowupArgs) -> ToolResult:
    with ctx.session() as db:
        out = followup_service.add_followup(
            db, ctx.user, FollowupCreate(**args.model_dump()), source="agent"
        )
    return ToolResult(ok=True, summary="已记录跟进", data=out.model_dump(mode="json"))


class UpdateStageArgs(BaseModel):
    opportunity_id: uuid.UUID
    stage: Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
    idempotency_key: str = Field(min_length=1, max_length=100)


def update_opportunity_stage(ctx: ToolContext, args: UpdateStageArgs) -> ToolResult:
    with ctx.session() as db:
        out = opp_service.update_stage(db, ctx.user, args.opportunity_id, args.stage, "agent")
    return ToolResult(ok=True, summary=f"阶段已改为 {out.stage}", data=out.model_dump(mode="json"))


class EmptyArgs(BaseModel):
    pass


def pipeline_summary(ctx: ToolContext, args: EmptyArgs) -> ToolResult:
    with ctx.session() as db:
        stages = opp_service.pipeline_summary(db, ctx.user)
    total = sum(s.count for s in stages)
    return ToolResult(ok=True, summary=f"共 {total} 个商机", data=[s.model_dump() for s in stages])


class CalcCommissionArgs(BaseModel):
    lines: list[CommissionLineIn]
    margin_rate: float = Field(ge=-1, le=1)
    paid_ratio: float = Field(default=1.0, ge=0, le=1)


def calc_commission(ctx: ToolContext, args: CalcCommissionArgs) -> ToolResult:
    result = finance_service.estimate_commission(CommissionEstimateIn(**args.model_dump()))
    summary = f"预计提成 ¥{result.estimated / 100:,.0f}" + (
        "（低毛利减半）" if result.halved else ""
    )
    return ToolResult(ok=True, summary=summary, data=result.model_dump())


class SubmitExpenseArgs(BaseModel):
    type: str = "entertainment"
    amount: int = Field(gt=0, description="金额（分）")
    headcount: int = Field(default=1, ge=1)
    occurred_on: date
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    reason: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=100)


def submit_expense(ctx: ToolContext, args: SubmitExpenseArgs) -> ToolResult:
    data = ExpenseCreate(**args.model_dump())
    with ctx.session() as db:
        out = finance_service.submit_expense(db, ctx.user, data)
    return ToolResult(ok=True, summary="报销单已提交", data=out)


CRM_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "search_customer", "模糊匹配客户，匹配到多个时让用户选", SearchCustomerArgs, search_customer
    ),
    ToolSpec("add_followup", "记录跟进", AddFollowupArgs, add_followup, write=True),
    ToolSpec(
        "update_opportunity_stage",
        "修改商机阶段",
        UpdateStageArgs,
        update_opportunity_stage,
        write=True,
        needs_confirm=True,
    ),
    ToolSpec("pipeline_summary", "商机漏斗统计", EmptyArgs, pipeline_summary),
    ToolSpec("calc_commission", "按 rules.yaml 计算提成", CalcCommissionArgs, calc_commission),
    ToolSpec(
        "submit_expense",
        "提交报销（提交前先做制度校验）",
        SubmitExpenseArgs,
        submit_expense,
        write=True,
        needs_confirm=True,
    ),
]
