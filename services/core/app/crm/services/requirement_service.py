"""商机需求清单：出方案时 AI 拆出的需求，保存在商机上，下次出方案接着用。

- 待确认：AI 根据描述拆的初稿 + 粗估价格区间 + 建议和客户确认的问题；
- 已确认：销售在需求卡片上逐项核对过，之后出方案直接按它报价。
需求内容由行业包的 requirement_model 定义（软件外包：交付端 + 功能模块），这里只按 JSON 保存。
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.services import activity_service
from app.crm.services import opportunity_service as opp_service


class RequirementOut(BaseModel):
    pack: str
    data: dict[str, Any]
    confirmed: bool = False
    # 粗估价格区间（分）：低 = 只做客户提到的功能的经济版，高 = 全部功能的高配版
    price_low: int | None = None
    price_high: int | None = None
    questions: list[str] = Field(default_factory=list)  # 建议和客户确认的问题
    updated_at: datetime
    updated_by: str | None = None


def get_requirement(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID
) -> RequirementOut | None:
    opp = opp_service.get_opportunity(db, user, opportunity_id)
    return RequirementOut.model_validate(opp.requirement) if opp.requirement else None


def save_requirement(
    db: Session,
    user: CurrentUser,
    opportunity_id: uuid.UUID,
    *,
    pack: str,
    data: dict[str, Any],
    confirmed: bool,
    price_low: int | None = None,
    price_high: int | None = None,
    questions: list[str] | None = None,
) -> RequirementOut:
    """只有负责人本人可以保存；第一次确认时记一条商机动态。"""
    opp = opp_service.get_owned(db, user, opportunity_id)
    old = opp.requirement or {}
    was_confirmed = bool(old.get("confirmed"))
    # 确认时不重新估区间：沿用上次的粗估和问题
    record = RequirementOut(
        pack=pack,
        data=data,
        confirmed=confirmed,
        price_low=price_low if price_low is not None else old.get("price_low"),
        price_high=price_high if price_high is not None else old.get("price_high"),
        questions=questions if questions is not None else old.get("questions", []),
        updated_at=datetime.now(UTC),
        updated_by=user.name,
    )
    opp.requirement = record.model_dump(mode="json")  # 整体赋值，让 SQLAlchemy 识别 JSONB 变化
    db.flush()
    if confirmed and not was_confirmed:
        modules = data.get("modules") or []
        activity_service.record(
            db, user, "opportunity", opp.id, "requirement_confirmed",
            f"{len(modules)} 个功能模块" if modules else "", subject=opp,
        )  # fmt: skip
    return record
