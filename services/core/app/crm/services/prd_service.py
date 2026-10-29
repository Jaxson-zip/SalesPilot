"""PRD 规格书：按商机上保存的需求清单生成，存在商机上，之后直接读取。

- 只有软件外包的需求清单可以生成（其他行业包的需求只是几个参数）；
- 负责人本人生成 / 重新生成；能看到商机的人都能查看；
- 需求清单之后改过（updated_at 变了）时标 stale，提示重新生成。
"""

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer
from app.crm.models import Customer
from app.crm.services import activity_service
from app.crm.services import opportunity_service as opp_service
from app.packs.software_outsourcing import prd_generator
from app.packs.software_outsourcing.requirement import SoftwareRequirement

logger = logging.getLogger("core.prd")
PRD_PACK = "software_outsourcing"


class PrdOut(BaseModel):
    markdown: str
    source: Literal["ai", "template"]  # 模型扩写 / 模型不可用时的模板版
    generated_at: datetime
    generated_by: str
    requirement_at: datetime  # 生成时需求清单的更新时间
    confirmed: bool  # 生成时需求清单是否已和客户确认
    stale: bool = False  # 需求清单之后又改过


@dataclass
class PrdJob:
    """一次生成需要的全部输入（校验通过后才创建）。"""

    opportunity_id: uuid.UUID
    template: str
    messages: list[BaseMessage]
    requirement_at: datetime
    confirmed: bool


def get_prd(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> PrdOut | None:
    opp = opp_service.get_opportunity(db, user, opportunity_id)
    if not opp.prd:
        return None
    out = PrdOut.model_validate(opp.prd)
    req_at = (opp.requirement or {}).get("updated_at")
    out.stale = req_at is not None and datetime.fromisoformat(req_at) != out.requirement_at
    return out


def prepare(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> PrdJob:
    """校验并准备生成：负责人本人、软件外包、已有需求清单。"""
    ensure_business_writer(user)
    opp = opp_service.get_owned(db, user, opportunity_id)
    record = opp.requirement or {}
    if not record.get("data"):
        raise BizError(ErrorCode.VALIDATION, "这个商机还没有需求清单，先在 AI 工作台出一次方案")
    if record.get("pack") != PRD_PACK:
        raise BizError(ErrorCode.VALIDATION, "只有软件外包项目可以生成 PRD 规格书")
    req = SoftwareRequirement.model_validate(record["data"])
    customer = db.get(Customer, opp.customer_id)
    confirmed = bool(record.get("confirmed"))
    template = prd_generator.skeleton(
        req, title=opp.name, customer=customer.name if customer else "—", confirmed=confirmed
    )
    return PrdJob(
        opportunity_id=opp.id,
        template=template,
        messages=prd_generator.messages(req, template),
        requirement_at=datetime.fromisoformat(record["updated_at"]),
        confirmed=confirmed,
    )


def save(
    db: Session, user: CurrentUser, job: PrdJob, markdown: str, source: Literal["ai", "template"]
) -> PrdOut:
    opp = opp_service.get_owned(db, user, job.opportunity_id)
    out = PrdOut(
        markdown=markdown,
        source=source,
        generated_at=datetime.now(UTC),
        generated_by=user.name,
        requirement_at=job.requirement_at,
        confirmed=job.confirmed,
    )
    opp.prd = out.model_dump(mode="json", exclude={"stale"})
    db.flush()
    label = "AI 扩写" if source == "ai" else "模板版"
    activity_service.record(
        db, user, "opportunity", opp.id, "prd", f"生成 PRD 规格书（{label}）", subject=opp
    )
    return out


def run(user: CurrentUser, job: PrdJob, llm: Any) -> Iterator[dict[str, Any]]:
    """流式生成（事件与 AI 对话一致）：message.delta 逐字 → artifact{type: prd} 最终全文 → done。

    模型不可用或中途失败时用模板版（artifact 里的全文覆盖已经显示的部分）。
    """
    parts: list[str] = []
    text, source = job.template, "template"
    if llm is not None:
        try:
            for chunk in llm.stream(job.messages):
                piece = chunk.content if isinstance(chunk.content, str) else ""
                if piece:
                    parts.append(piece)
                    yield {"event": "message.delta", "data": {"text": piece}}
            if "".join(parts).strip():
                text, source = prd_generator.finalize("".join(parts)), "ai"
        except Exception:
            logger.warning("prd: llm failed, fallback to template", exc_info=True)
    try:
        with session_scope() as db:
            out = save(db, user, job, text, source)  # type: ignore[arg-type]
    except BizError as e:
        yield {"event": "error", "data": {"code": e.code, "message": e.message}}
    else:
        yield {"event": "artifact", "data": {"type": "prd", "data": out.model_dump(mode="json")}}
    yield {"event": "done", "data": {}}
