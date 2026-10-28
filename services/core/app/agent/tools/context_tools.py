"""上下文查询工具：给模型提供后续写操作需要的 id（商机、联系人），只读。

模型先用 search_customer 找到客户，再用 get_customer_context 拿到该客户的商机和联系人，
之后才能调用 update_opportunity_stage / submit_expense / create_task 等写工具。
"""

import uuid

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.schemas.common import PageParams
from app.crm.schemas.dashboard import CONTACT_ROLE_LABELS
from app.crm.schemas.opportunity import STAGE_LABELS
from app.crm.services import (
    approval_service,
    competitor_service,
    contact_service,
    meddic_service,
)
from app.crm.services import opportunity_service as opp_service


class CustomerContextArgs(BaseModel):
    customer_id: uuid.UUID = Field(description="search_customer 返回的客户 id")


def get_customer_context(ctx: ToolContext, args: CustomerContextArgs) -> ToolResult:
    """客户的商机（含阶段、金额、下一步）和联系人；权限与接口一致（看不到的客户返回 40401）。"""
    with ctx.session() as db:
        contacts = contact_service.list_contacts(db, ctx.user, args.customer_id).items
        opps = opp_service.list_opportunities(
            db, ctx.user, None, PageParams(page=1, page_size=20), customer_id=args.customer_id
        ).items
    data = {
        "opportunities": [
            {
                "id": str(o.id),
                "name": o.name,
                "stage": o.stage,
                "stage_label": STAGE_LABELS[o.stage],
                "amount": o.amount,
                "next_task": o.next_task.title if o.next_task else None,
                "idle_days": o.idle_days,
            }
            for o in opps
        ],
        "contacts": [
            {
                "id": str(c.id),
                "name": c.name,
                "title": c.title,
                "decision_maker": c.is_decision_maker,
                "role": CONTACT_ROLE_LABELS.get(c.role or ""),
            }
            for c in contacts
        ],
    }
    summary = f"{len(opps)} 个商机，{len(contacts)} 位联系人"
    return ToolResult(ok=True, summary=summary, data=data)


class PendingApprovalsArgs(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


def list_pending_approvals(ctx: ToolContext, args: PendingApprovalsArgs) -> ToolResult:
    """主管待处理的审批（本团队）；返回审批 id，decide_approval 需要它。"""
    with ctx.session() as db:
        page = approval_service.list_approvals(
            db, ctx.user, "pending", PageParams(page=1, page_size=args.limit)
        )
    data = [
        {
            "approval_id": str(a.id),
            "target_type": a.target_type,
            "target": a.target.model_dump(mode="json"),
            "reason": a.reason,
            "ai_suggestion": a.ai_suggestion,
        }
        for a in page.items
    ]
    return ToolResult(ok=True, summary=f"待审批 {page.total} 条", data=data)


class MeddicArgs(BaseModel):
    opportunity_id: uuid.UUID = Field(description="get_customer_context 返回的商机 id")


def get_meddic(ctx: ToolContext, args: MeddicArgs) -> ToolResult:
    """商机的 MEDDIC 赢单要素：已确认 / 待验证 / 缺失，当前阶段的风险项和建议问题。"""
    with ctx.session() as db:
        out = meddic_service.get_meddic(db, ctx.user, args.opportunity_id)
    data = {
        "score": out.score,
        "risks": out.risks,
        "items": [
            {
                "label": i.label,
                "status": {"confirmed": "已确认", "partial": "待验证", "missing": "缺失"}[i.status],
                "evidence": i.evidence,
                "questions": i.questions,
            }
            for i in out.items
        ],
    }
    risk = f"，风险：{'、'.join(out.risks)}" if out.risks else ""
    return ToolResult(ok=True, summary=f"赢单要素完成度 {out.score}%{risk}", data=data)


class BattlecardArgs(BaseModel):
    keyword: str | None = Field(
        default=None, max_length=200, description="竞品叫法或客户原话，例如「云上 API 更便宜」"
    )
    opportunity_id: uuid.UUID | None = Field(default=None, description="查这个商机标注的竞品")


def get_battlecard(ctx: ToolContext, args: BattlecardArgs) -> ToolResult:
    """竞品战卡：优势、弱点、我们怎么赢、常见说法与应对、历史战绩。"""
    with ctx.session() as db:
        cards = competitor_service.find_for_chat(db, ctx.user, args.keyword, args.opportunity_id)
    data = [competitor_service.as_dict(c) for c in cards[:3]]
    if not cards:
        return ToolResult(ok=True, summary="战卡库里没有匹配的竞品", data=[])
    return ToolResult(ok=True, summary=f"找到 {len(cards)} 张战卡：{cards[0].name}", data=data)


CONTEXT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "get_battlecard",
        "查竞品战卡（竞品优势、弱点、我们怎么赢、常见说法与应对话术、输赢战绩）。"
        "用户提到竞品、客户拿别家比价、或问「客户说 xxx 怎么回」时使用",
        BattlecardArgs,
        get_battlecard,
    ),
    ToolSpec(
        "get_meddic",
        "查询商机的 MEDDIC 赢单要素（痛点、量化收益、经济决策人、决策标准、决策流程、内部支持者）"
        "的完成情况、当前阶段的风险和建议问题。用户问单子怎么推进、赢面、风险、下一步该见谁时使用",
        MeddicArgs,
        get_meddic,
    ),
    ToolSpec(
        "get_customer_context",
        "查询客户的商机（id、阶段、金额、下一步）和联系人（id、姓名、职务）。"
        "修改商机阶段、报销选参与人、建任务之前先调用它拿到 id",
        CustomerContextArgs,
        get_customer_context,
    ),
    ToolSpec(
        "list_pending_approvals",
        "列出主管待处理的审批（报价 / 报销），返回 approval_id、单号、金额、超标原因",
        PendingApprovalsArgs,
        list_pending_approvals,
    ),
]
