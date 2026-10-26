"""商机 service（接口契约 §2）：列表 / 详情 / 新建 / 修改 / 阶段流转 / 漏斗 / 行业包解析。"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.scope import View, apply_scope, can_see, ensure_visible
from app.crm.models import Customer, Opportunity, ProductLine, Team
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.opportunity import (
    FINAL_STAGES,
    STAGE_LABELS,
    STAGES,
    OpportunityCreate,
    OpportunityDetail,
    OpportunityItem,
    OpportunityUpdate,
    PipelineStage,
    PipelineSummary,
    StageChange,
)
from app.crm.services import activity_service, lookup, quote_query
from app.rules import weighted_amount

RULE_STAGE_FINAL = "opportunity_stage_final"


def get_opportunity(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> Opportunity:
    """取单条商机并校验可见性（看不到返回 40401）。"""
    opp = db.get(Opportunity, opportunity_id)
    ensure_visible(opp, user)
    assert opp is not None
    return opp


def to_items(db: Session, opps: list[Opportunity]) -> list[OpportunityItem]:
    customers = lookup.customers(db, (o.customer_id for o in opps))
    owners = lookup.users(db, (o.owner_id for o in opps))
    lines = lookup.product_lines(db, (o.product_line_id for o in opps))
    return [
        OpportunityItem(
            id=o.id,
            name=o.name,
            customer=customers[o.customer_id],
            stage=o.stage,  # type: ignore[arg-type]
            amount=o.amount,
            win_rate=o.win_rate,
            expected_close_date=o.expected_close_date,
            product_line=lookup.pick(lines, o.product_line_id),
            owner=lookup.pick(owners, o.owner_id),
            lost_reason=o.lost_reason,
            updated_at=o.updated_at,
        )
        for o in opps
    ]


def build_query(
    user: CurrentUser,
    view: View | None,
    stage: str | None = None,
    customer_id: uuid.UUID | None = None,
    q: str | None = None,
) -> Select[Any]:
    stmt = select(Opportunity).join(Customer, Customer.id == Opportunity.customer_id)
    if stage:
        stmt = stmt.where(Opportunity.stage == stage)
    if customer_id:
        stmt = stmt.where(Opportunity.customer_id == customer_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Opportunity.name.ilike(pattern), Customer.name.ilike(pattern)))
    return apply_scope(stmt, Opportunity, user, view)


def list_opportunities(
    db: Session,
    user: CurrentUser,
    view: View | None,
    page: PageParams,
    stage: str | None = None,
    customer_id: uuid.UUID | None = None,
    q: str | None = None,
) -> Page[OpportunityItem]:
    base = build_query(user, view, stage, customer_id, q)
    total = quote_query.count(db, base)
    stmt = base.order_by(Opportunity.updated_at.desc(), Opportunity.id)
    opps = list(db.scalars(stmt.offset(page.offset).limit(page.page_size)).all())
    return Page[OpportunityItem](items=to_items(db, opps), total=total)


def get_item(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> OpportunityItem:
    db.flush()
    opp = get_opportunity(db, user, opportunity_id)
    db.refresh(opp)
    return to_items(db, [opp])[0]


def get_detail(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> OpportunityDetail:
    item = get_item(db, user, opportunity_id)
    return OpportunityDetail(
        **item.model_dump(),
        quotes=quote_query.list_for_opportunity(db, user, opportunity_id),
        activities=activity_service.list_for_subject(db, opportunity_id),
    )


def _check_product_line(db: Session, product_line_id: uuid.UUID | None) -> None:
    if product_line_id is None:
        return
    line = db.get(ProductLine, product_line_id)
    if line is None or not line.enabled:
        raise BizError(
            ErrorCode.VALIDATION,
            "产品线不存在或未启用",
            {"errors": [{"loc": ["body", "product_line_id"], "msg": "产品线不存在或未启用"}]},
        )


def create_opportunity(db: Session, user: CurrentUser, data: OpportunityCreate) -> OpportunityItem:
    customer = db.get(Customer, data.customer_id)
    if customer is None or not can_see(customer, user):
        raise BizError(ErrorCode.NOT_FOUND, "客户不存在")
    _check_product_line(db, data.product_line_id)
    opp = Opportunity(**data.model_dump(), stage="lead", owner_id=user.id, team_id=user.team_id)
    opp.name = data.name.strip()
    db.add(opp)
    db.flush()
    activity_service.record(
        db, user, "opportunity", opp.id, "create", f"创建了商机 {opp.name}", subject=opp
    )
    return get_item(db, user, opp.id)


def update_opportunity(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID, data: OpportunityUpdate
) -> OpportunityItem:
    opp = get_opportunity(db, user, opportunity_id)
    changes = data.model_dump(exclude_unset=True)
    if "product_line_id" in changes:
        _check_product_line(db, changes["product_line_id"])
    for key, value in changes.items():
        if value is None and key in {"name", "amount", "win_rate"}:
            continue  # 非空字段传 null 视为不修改
        setattr(opp, key, value.strip() if key == "name" else value)
    if changes:
        activity_service.record(
            db, user, "opportunity", opp.id, "updated", _describe(changes), subject=opp
        )
    return get_item(db, user, opp.id)


def _describe(changes: dict[str, Any]) -> str:
    labels = {
        "name": "名称",
        "amount": "金额",
        "win_rate": "赢率",
        "expected_close_date": "预计成交日",
        "product_line_id": "产品线",
    }
    return "修改了" + "、".join(labels.get(k, k) for k in changes)


def apply_stage(
    db: Session,
    user: CurrentUser,
    opp: Opportunity,
    change: StageChange,
    source: str = "manual",
) -> None:
    """阶段流转（规则校验 + 写动态），接口、Agent 工具和报价成交共用。"""
    if opp.stage in FINAL_STAGES:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"商机已{STAGE_LABELS[opp.stage]}，不能再修改阶段",
            {"rule": RULE_STAGE_FINAL, "stage": opp.stage},
        )
    if change.stage == opp.stage:
        return
    old = opp.stage
    opp.stage = change.stage
    if change.stage in FINAL_STAGES:
        opp.closed_at = datetime.now(UTC)
    content = f"{STAGE_LABELS[old]} → {STAGE_LABELS[change.stage]}"
    if change.stage == "lost":
        opp.lost_reason = (change.lost_reason or "").strip()
        content += f"（原因：{opp.lost_reason}）"
    db.flush()
    activity_service.record(
        db, user, "opportunity", opp.id, "stage_changed", content, source, subject=opp
    )


def change_stage(
    db: Session,
    user: CurrentUser,
    opportunity_id: uuid.UUID,
    change: StageChange,
    source: str = "manual",
) -> OpportunityItem:
    opp = get_opportunity(db, user, opportunity_id)
    apply_stage(db, user, opp, change, source)
    return get_item(db, user, opp.id)


def _stage_rows(db: Session, user: CurrentUser, view: View | None) -> list[Any]:
    stmt = select(
        Opportunity.stage,
        func.count(),
        func.coalesce(func.sum(Opportunity.amount), 0),
    ).group_by(Opportunity.stage)
    return list(db.execute(apply_scope(stmt, Opportunity, user, view)).all())


def funnel(db: Session, user: CurrentUser, view: View | None = None) -> list[PipelineStage]:
    counts = {stage: (int(c), int(a)) for stage, c, a in _stage_rows(db, user, view)}
    return [
        PipelineStage(stage=s, count=counts.get(s, (0, 0))[0], amount=counts.get(s, (0, 0))[1])
        for s in STAGES
    ]


def pipeline_summary(db: Session, user: CurrentUser, view: View | None = None) -> PipelineSummary:
    """漏斗 + 合计：total / weighted 不含输单（lost）。"""
    stages = funnel(db, user, view)
    stmt = apply_scope(
        select(Opportunity.amount, Opportunity.win_rate).where(Opportunity.stage != "lost"),
        Opportunity,
        user,
        view,
    )
    pairs = [(int(a), int(w)) for a, w in db.execute(stmt).all()]
    return PipelineSummary(
        stages=stages,
        total_amount=sum(a for a, _ in pairs),
        weighted_amount=weighted_amount(pairs),
    )


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
