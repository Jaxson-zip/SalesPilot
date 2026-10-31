"""一手材料消化：会议纪要 / 聊天记录 / 名片整理成「跟进 + 联系人 + 下一步」，确认一次全部写入。

模型从材料里抽取，工具只负责写库：同一个事务里记跟进、补联系人（同名的只补空字段，不覆盖）、
建任务；任何一步失败整体回滚，不会出现「跟进记了、联系人没加」的半截数据。
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.models import Contact
from app.crm.schemas.dashboard import ContactIn, ContactRole
from app.crm.schemas.fields import ContactName, Phone
from app.crm.schemas.task import TaskCreate, TaskType
from app.crm.services import contact_service, followup_service, task_service
from app.crm.services.followup_service import FollowupCreate


class MaterialContact(BaseModel):
    name: ContactName
    title: str | None = Field(default=None, max_length=50, description="职务")
    phone: Phone = None
    role: ContactRole | None = Field(
        default=None,
        description="decision_maker 决策人 / influencer 影响者 / technical 技术 / "
        "finance 财务 / user 使用者；看不出来就不填",
    )


class MaterialStep(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime = Field(description="北京时间 ISO 格式；材料没写日期就按语境估一个合理时间")
    type: TaskType = "todo"


class DigestMaterialArgs(BaseModel):
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    followup_type: Literal["phone", "visit", "wechat"] = Field(
        default="visit",
        description="材料对应的沟通方式：拜访 / 会议纪要用 visit，聊天记录用 wechat",
    )
    summary: str = Field(
        min_length=1,
        max_length=2000,
        description="跟进记录正文，分两段、每段分条："
        "「跟进重点：」沟通结论、进展、预算 / 时间；「客户关注点：」需求与痛点、顾虑、提到的竞品",
    )
    contacts: list[MaterialContact] = Field(default_factory=list, max_length=20)
    next_steps: list[MaterialStep] = Field(default_factory=list, max_length=10)


def digest_material(ctx: ToolContext, args: DigestMaterialArgs) -> ToolResult:
    added: list[str] = []
    updated: list[str] = []
    with ctx.session() as db:
        followup_service.add_followup(
            db,
            ctx.user,
            FollowupCreate(
                customer_id=args.customer_id,
                opportunity_id=args.opportunity_id,
                type=args.followup_type,
                content=args.summary,
            ),
            source="agent",
        )
        existing = {
            c.name: c
            for c in db.scalars(select(Contact).where(Contact.customer_id == args.customer_id))
        }
        for person in args.contacts:
            name = person.name.strip()
            old = existing.get(name)
            if old is None:
                contact_service.create_contact(
                    db, ctx.user, args.customer_id, ContactIn(**person.model_dump())
                )
                added.append(name)
                continue
            # 已有的联系人只补空字段，不覆盖销售手工维护的信息
            changed = False
            for field in ("title", "phone", "role"):
                value = getattr(person, field)
                if value and not getattr(old, field):
                    setattr(old, field, value)
                    changed = True
            if changed:
                old.is_decision_maker = old.role == "decision_maker"
                updated.append(name)
        subject_type = "opportunity" if args.opportunity_id else "customer"
        subject_id = args.opportunity_id or args.customer_id
        for step in args.next_steps:
            task_service.create_task(
                db,
                ctx.user,
                TaskCreate(
                    title=step.title,
                    due_at=step.due_at,
                    type=step.type,
                    subject_type=subject_type,
                    subject_id=subject_id,
                ),
                source="agent",
            )
    parts = ["已记录 1 条跟进"]
    if added:
        parts.append(f"新增联系人 {'、'.join(added)}")
    if updated:
        parts.append(f"补充了 {'、'.join(updated)} 的信息")
    if args.next_steps:
        parts.append(f"安排 {len(args.next_steps)} 项下一步")
    data = {
        "customer_id": str(args.customer_id),
        "contacts_added": added,
        "contacts_updated": updated,
        "tasks": len(args.next_steps),
    }
    return ToolResult(ok=True, summary="，".join(parts), data=data)


MATERIAL_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "digest_material",
        "把用户上传或粘贴的一手材料（会议纪要、聊天记录、录音转写、名片）整理后一次写入："
        "跟进记录 + 联系人 + 下一步任务。"
        "先用 search_customer / get_customer_context 确认客户和商机；"
        "summary 按「跟进重点」「客户关注点」两段分条写，"
        "contacts 只写材料里出现的客户方人员（不要写我方同事），"
        "next_steps 写材料里约定或明显需要的后续动作",
        DigestMaterialArgs,
        digest_material,
        write=True,
        needs_confirm=True,
    ),
]
