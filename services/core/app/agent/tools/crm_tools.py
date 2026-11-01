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
    ExpenseDetails,
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
    progress_service,
    task_service,
)
from app.crm.services import opportunity_service as opp_service
from app.crm.services.progress_service import ActiveStage, NextStepIn, ProgressIn
from app.rules.crm_calc import LOCAL_TZ


class SearchCustomerArgs(BaseModel):
    keyword: str = Field(
        min_length=1, max_length=200, description="客户名称关键字；也可以是商机名（如「质检助手」）"
    )


def search_customer(ctx: ToolContext, args: SearchCustomerArgs) -> ToolResult:
    """按客户名找；找不到再按商机名找（回归：「质检助手那单丢了」查客户名查不到就卡住了）。"""
    with ctx.session() as db:
        found = customer_service.search_customers(db, ctx.user, args.keyword)
        by_opp = [] if found else customer_service.search_by_opportunity(db, ctx.user, args.keyword)
    if by_opp:
        data = [{**c.model_dump(mode="json"), "matched_opportunity": o} for c, o in by_opp]
        names = "、".join(f"{c.name}（商机「{o}」）" for c, o in by_opp)
        return ToolResult(ok=True, summary=f"客户名没匹配到，按商机名找到：{names}", data=data)
    data = [c.model_dump(mode="json") for c in found]
    if not found:
        return ToolResult(ok=True, summary="没有匹配的客户或商机", data=data)
    if len(found) > 1:
        return ToolResult(ok=True, summary=f"匹配到 {len(found)} 个客户，请确认", data=data)
    return ToolResult(ok=True, summary=found[0].name, data=data)


class AddFollowupArgs(BaseModel):
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    type: Literal["phone", "visit", "wechat", "ai"] = "phone"
    content: str = Field(min_length=1, max_length=2000)
    next_step: NextStepIn | None = Field(
        default=None,
        description="用户这次说到的下一步（谁什么时候做什么），due_at 用北京时间 ISO 格式；"
        "没说就不填",
    )
    stage: ActiveStage | None = Field(
        default=None,
        description="用户明确说商机推进到了某个阶段时才填（需要 opportunity_id）；"
        "赢单 / 输单不在这里填，用 update_opportunity_stage",
    )


def add_followup(ctx: ToolContext, args: AddFollowupArgs) -> ToolResult:
    """跟进、下一步、阶段一个事务写入（progress_service），任何一步失败都不留半截数据。"""
    with ctx.session() as db:
        out = progress_service.record_progress(
            db, ctx.user, ProgressIn(**args.model_dump()), source="agent"
        )
    parts = ["已记录跟进"]
    if out.task:
        parts.append(f"安排了「{out.task.title}」")
    if out.opportunity:
        parts.append(f"阶段改为「{STAGE_LABELS[out.opportunity.stage]}」")
    data = {
        **out.followup.model_dump(mode="json"),
        "task": out.task.model_dump(mode="json") if out.task else None,
        "stage": out.opportunity.stage if out.opportunity else None,
    }
    return ToolResult(ok=True, summary="，".join(parts), data=data)


class UpdateStageArgs(StageChange):
    """继承 StageChange：输单必须写原因的校验在参数阶段完成（失败返回 40001，而不是 50001）。"""

    opportunity_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=100)


def update_opportunity_stage(ctx: ToolContext, args: UpdateStageArgs) -> ToolResult:
    """复用接口的阶段校验（终态不能再改、输单必须写原因）。"""
    change = StageChange(stage=args.stage, lost_reason=args.lost_reason, quote_id=args.quote_id)
    with ctx.session() as db:
        out = opp_service.change_stage(db, ctx.user, args.opportunity_id, change, "agent")
    summary = f"阶段已改为「{STAGE_LABELS[out.stage]}」"
    if args.quote_id:
        summary += "，已按报价生成合同和回款计划"
    return ToolResult(ok=True, summary=summary, data=out.model_dump(mode="json"))


class EmptyArgs(BaseModel):
    pass


def pipeline_summary(ctx: ToolContext, args: EmptyArgs) -> ToolResult:
    with ctx.session() as db:
        out = opp_service.pipeline_summary(db, ctx.user)
    total = sum(s.count for s in out.stages)
    # 累计口径：不分月份、不按人拆分（回归：模型把累计赢单说成「本月」）
    summary = f"共 {total} 个商机（累计口径，不分月份、不按人；本月业绩和按人对比用 team_targets）"
    return ToolResult(ok=True, summary=summary, data=out.model_dump())


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
    details: ExpenseDetails | None = Field(
        default=None, description="差旅住宿必填 city / check_in / check_out；差旅交通可填行程"
    )


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
        "search_customer",
        "按名称模糊匹配客户（返回 id）。匹配到多个时先让用户选，不要自己猜",
        SearchCustomerArgs,
        search_customer,
    ),
    ToolSpec(
        "add_followup",
        "给客户记一条跟进记录。content 写清沟通内容、客户反馈和下一步；"
        "type：phone 电话、visit 拜访、wechat 微信。"
        "同一次沟通里说到的下一步（next_step）和阶段推进（stage）一起填在这一条里，"
        "只弹一张确认卡，不要拆成 add_followup + create_task + update_opportunity_stage 多次调用；"
        "用户没说的下一步和阶段不填，也不要为此追问：直接记，确认卡上用户自己能看到",
        AddFollowupArgs,
        add_followup,
        write=True,
        needs_confirm=True,
    ),
    ToolSpec(
        "update_opportunity_stage",
        "修改商机阶段（lead 线索 / qualified 需求确认 / proposal 方案报价 / negotiation 商务谈判 / "
        "won 赢单 / lost 输单，输单必须写 lost_reason）。opportunity_id 来自 get_customer_context。"
        "赢单时若该商机有已审批 / 已发送的报价，传 quote_id 按该报价成交（生成合同和回款计划）。"
        "用户同时讲了这次沟通的内容（拜访、电话里客户怎么说）时，非赢单 / 输单的推进"
        "改用 add_followup 的 stage 一起写",
        UpdateStageArgs,
        update_opportunity_stage,
        write=True,
        needs_confirm=True,
    ),
    ToolSpec(
        "pipeline_summary",
        "统计当前用户可见的商机漏斗（各阶段数量和金额）",
        EmptyArgs,
        pipeline_summary,
    ),
    ToolSpec(
        "calc_commission",
        "按提成制度（rules.yaml）估算提成；金额单位为分，margin_rate 为 0–1 的小数",
        CalcCommissionArgs,
        calc_commission,
    ),
    ToolSpec(
        "submit_expense",
        "新建并提交报销单（系统自动做制度校验，超标会转主管审批）。"
        "amount 单位为分（860 元 = 86000）；客户招待要带 customer_id，"
        "contact_names 写客户方参与人姓名，colleague_names 写我方同事；occurred_on 用 YYYY-MM-DD；"
        "差旅住宿要在 details 里写城市和入住 / 离店日期（按每晚标准校验）",
        SubmitExpenseArgs,
        submit_expense,
        write=True,
        needs_confirm=True,
    ),
    ToolSpec(
        "create_task",
        "给自己负责的客户或商机安排下一步任务。subject_type 为 customer 或 opportunity，"
        "due_at 用北京时间 ISO 格式，type：call / visit / email / meeting / todo",
        TaskCreate,
        create_task,
        write=True,
        needs_confirm=True,
    ),
    ToolSpec(
        "decide_approval",
        "主管通过或驳回审批（报价 / 报销），驳回时写明原因",
        DecideApprovalArgs,
        decide_approval,
        write=True,
        needs_confirm=True,
    ),
]
