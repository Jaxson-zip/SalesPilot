"""上下文查询工具：给模型提供后续写操作需要的 id（商机、联系人），只读。

模型先用 search_customer 找到客户，再用 get_customer_context 拿到该客户的商机和联系人，
之后才能调用 update_opportunity_stage / submit_expense / create_task 等写工具。
"""

import uuid

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.schemas.common import PageParams
from app.crm.schemas.opportunity import STAGE_LABELS
from app.crm.services import customer_service
from app.crm.services import opportunity_service as opp_service


class CustomerContextArgs(BaseModel):
    customer_id: uuid.UUID = Field(description="search_customer 返回的客户 id")


def get_customer_context(ctx: ToolContext, args: CustomerContextArgs) -> ToolResult:
    """客户的商机（含阶段、金额、下一步）和联系人；权限与接口一致（看不到的客户返回 40401）。"""
    with ctx.session() as db:
        contacts = customer_service.list_contacts(db, ctx.user, args.customer_id).items
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
            }
            for c in contacts
        ],
    }
    summary = f"{len(opps)} 个商机，{len(contacts)} 位联系人"
    return ToolResult(ok=True, summary=summary, data=data)


CONTEXT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "get_customer_context",
        "查询客户的商机（id、阶段、金额、下一步）和联系人（id、姓名、职务）。"
        "修改商机阶段、报销选参与人、建任务之前先调用它拿到 id",
        CustomerContextArgs,
        get_customer_context,
    ),
]
