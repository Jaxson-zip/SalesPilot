"""商机 service：阶段流转、漏斗统计、从产品线解析行业包。

TODO: list / create / update / 看板拖拽接口（参考 customer_service 实现）。
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.scope import apply_scope, ensure_visible
from app.crm.models import Opportunity, ProductLine, Team
from app.crm.schemas.opportunity import STAGES, OpportunityOut, PipelineStage
from app.crm.services import activity_service


def _to_out(o: Opportunity) -> OpportunityOut:
    return OpportunityOut.model_validate(o, from_attributes=True)


def get_opportunity(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> Opportunity:
    opp = db.get(Opportunity, opportunity_id)
    ensure_visible(opp, user)
    assert opp is not None
    return opp


def update_stage(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID, stage: str, source: str = "manual"
) -> OpportunityOut:
    if stage not in STAGES:
        raise BizError(ErrorCode.VALIDATION, f"未知阶段：{stage}")
    opp = get_opportunity(db, user, opportunity_id)
    if opp.stage in ("won", "lost"):
        raise BizError(ErrorCode.RULE_VIOLATION, "已结束的商机不能修改阶段", {"rule": "stage"})
    old = opp.stage
    opp.stage = stage
    db.flush()
    activity_service.record(
        db, user, "opportunity", opp.id, "stage", f"阶段：{old} → {stage}", source
    )
    return _to_out(opp)


def pipeline_summary(db: Session, user: CurrentUser) -> list[PipelineStage]:
    stmt = apply_scope(
        select(
            Opportunity.stage, func.count(), func.coalesce(func.sum(Opportunity.amount), 0)
        ).group_by(Opportunity.stage),
        Opportunity,
        user,
    )
    counts = {stage: (int(c), int(a)) for stage, c, a in db.execute(stmt).all()}
    return [
        PipelineStage(stage=s, count=counts.get(s, (0, 0))[0], amount=counts.get(s, (0, 0))[1])
        for s in STAGES
    ]


def resolve_pack(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID | None, default_pack: str
) -> str:
    """行业包由商机产品线带出；没有商机时用团队默认产品线；都没有时用系统默认行业包。"""
    product_line_id: uuid.UUID | None = None
    if opportunity_id is not None:
        product_line_id = get_opportunity(db, user, opportunity_id).product_line_id
    elif user.team_id is not None:
        team = db.get(Team, user.team_id)
        product_line_id = team.default_product_line_id if team else None
    if product_line_id is None:
        return default_pack
    line = db.get(ProductLine, product_line_id)
    if line is None or not line.enabled:
        raise BizError(ErrorCode.RULE_VIOLATION, "产品线未启用行业包", {"rule": "pack"})
    return line.pack
