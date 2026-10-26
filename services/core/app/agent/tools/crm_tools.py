"""CRM 类工具（开发规范 §6.2）：都是 service 的薄包装。"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.schemas.finance import (
    CommissionEstimateIn,
    CommissionLineIn,
    ExpenseCreate,
    ExpenseType,
)
from app.crm.schemas.opportunity import STAGE_LABELS, StageChange
from app.crm.schemas.task import TaskCreate
from app.crm.services import (
    approval_service,
    customer_service,
    expense_participants,
    expense_service,
    finance_service,
    followup_service,
    task_service,
)
from app.crm.services import opportunity_service as opp_service
from app.crm.services.followup_service import FollowupCreate
from app.rules.crm_calc import LOCAL_TZ


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


class UpdateStageArgs(StageChange):
    """继承 StageChange：输单必须写原因的校验在参数阶段完成（失败返回 40001，而不是 50001）。"""

    opportunity_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=100)


def update_opportunity_stage(ctx: ToolContext, args: UpdateStageArgs) -> ToolResult:
    """复用接口的阶段校验（终态不能再改、输单必须写原因）。"""
    change = StageChange(stage=args.stage, lost_reason=args.lost_reason)
    with ctx.session() as db:
        out = opp_service.change_stage(db, ctx.user, args.opportunity_id, change, "agent")
    summary = f"阶段已改为「{STAGE_LABELS[out.stage]}」"
    return ToolResult(ok=True, summary=summary, data=out.model_dump(mode="json"))


class EmptyArgs(BaseModel):
    pass


def pipeline_summary(ctx: ToolContext, args: EmptyArgs) -> ToolResult:
    with ctx.session() as db:
        out = opp_service.pipeline_summary(db, ctx.user)
    total = sum(s.count for s in out.stages)
    return ToolResult(ok=True, summary=f"共 {total} 个商机", data=out.model_dump())


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
    type: ExpenseType = "entertainment"
    amount: int = Field(gt=0, description="金额（分）")
    headcount: int | None = Field(default=None, ge=1, description="总人数（含本人），可不填")
    occurred_on: date
    participants: str | None = Field(
        default=None, max_length=500, description="对话里提到的参与人原文，用于匹配联系人和同事"
    )
    contact_names: list[str] = Field(default_factory=list, max_length=50)
    colleague_names: list[str] = Field(default_factory=list, max_length=50)
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=100)


EXPENSE_SUMMARIES = {
    "draft": "已创建报销草稿 {code}，请上传发票 / 小票后提交",
    "approved": "报销单 {code} 已提交，制度校验通过",
    "pending_approval": "报销单 {code} 已提交，超出标准，等待主管审批",
}


def submit_expense(ctx: ToolContext, args: SubmitExpenseArgs) -> ToolResult:
    """新建报销单（同时做制度校验）；票据齐全时直接提交。

    参与人：按人名匹配客户联系人和本团队同事，匹配不到的人数计入 extra_guests（契约 v3 §17）。
    """
    names = " ".join([args.participants or "", *args.contact_names, *args.colleague_names])
    data = ExpenseCreate(
        **args.model_dump(exclude={"headcount", "participants", "contact_names", "colleague_names"})
    )
    with ctx.session() as db:
        data = expense_participants.from_conversation(db, ctx.user, data, names, args.headcount)
        out = expense_service.create_and_submit(db, ctx.user, data, source="agent")
    summary = EXPENSE_SUMMARIES.get(out.status, "报销单 {code}").format(code=out.code)
    return ToolResult(ok=True, summary=summary, data=out.model_dump(mode="json"))


def create_task(ctx: ToolContext, args: TaskCreate) -> ToolResult:
    """给自己负责的客户 / 商机建下一步任务（契约 v3 §12）。"""
    with ctx.session() as db:
        out = task_service.create_task(db, ctx.user, args)
    due = out.due_at.astimezone(LOCAL_TZ).strftime("%m-%d %H:%M")
    summary = f"已创建任务「{out.title}」，{due} 到期"
    return ToolResult(ok=True, summary=summary, data=out.model_dump(mode="json"))


class DecideApprovalArgs(BaseModel):
    approval_id: uuid.UUID
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


def decide_approval(ctx: ToolContext, args: DecideApprovalArgs) -> ToolResult:
    """仅主管可用；已处理的审批返回 42201 approval_already_decided。"""
    with ctx.session() as db:
        out = approval_service.decide(
            db, ctx.user, args.approval_id, args.decision, args.comment, source="agent"
        )
    verb = "通过" if args.decision == "approve" else "驳回"
    summary = f"已{verb}审批：{out.target.code}"
    return ToolResult(ok=True, summary=summary, data=out.model_dump(mode="json"))


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
    ToolSpec(
        "create_task",
        "给自己负责的客户或商机创建下一步任务（到期时间、类型、备注）",
        TaskCreate,
        create_task,
        write=True,
        needs_confirm=True,
    ),
    ToolSpec(
        "decide_approval",
        "主管通过或驳回审批（报价 / 报销）",
        DecideApprovalArgs,
        decide_approval,
        write=True,
        needs_confirm=True,
    ),
]
