"""商机 service（接口契约 §2）：列表 / 详情 / 新建 / 修改 / 阶段流转 / 漏斗 / 行业包解析。"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.common.scope import View, apply_scope, ensure_visible
from app.crm.models import (
    Contract,
    Customer,
    Expense,
    Opportunity,
    ProductLine,
    Quote,
    Team,
    User,
)
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.opportunity import (
    FINAL_STAGES,
    STAGE_LABELS,
    STAGES,
    OpportunityCreate,
    OpportunityDetail,
    OpportunityExpenses,
    OpportunityItem,
    OpportunityProfit,
    OpportunityUpdate,
    PipelineStage,
    PipelineSummary,
    StageChange,
)
from app.crm.services import (
    activity_service,
    lookup,
    opportunity_insights,
    quote_query,
    wecom_service,
    won_rule,
)
from app.rules import load_rules, weighted_amount
from app.rules.crm_calc import default_win_rate

RULE_STAGE_FINAL = "opportunity_stage_final"


def get_opportunity(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> Opportunity:
    """取单条商机并校验可见性（看不到返回 40401）。"""
    opp = db.get(Opportunity, opportunity_id)
    ensure_visible(opp, user)
    assert opp is not None
    return opp


def get_owned(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> Opportunity:
    """取单条商机用于修改：只有负责人本人可以（接口契约 §0）。"""
    opp = db.get(Opportunity, opportunity_id)
    ensure_owner(opp, user)
    assert opp is not None
    return opp


def to_items(db: Session, opps: list[Opportunity]) -> list[OpportunityItem]:
    customers = lookup.customers(db, (o.customer_id for o in opps))
    owners = lookup.users(db, (o.owner_id for o in opps))
    lines = lookup.product_lines(db, (o.product_line_id for o in opps))
    extra = opportunity_insights.insights(db, opps)
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
            **extra[o.id],
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


def expense_summary(db: Session, opportunity_id: uuid.UUID) -> OpportunityExpenses:
    """关联到这单的报销：已批准（含已付款）和审批中的金额，草稿和被驳回的不算。"""
    rows = db.execute(
        select(Expense.status, func.count(), func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.opportunity_id == opportunity_id)
        .where(Expense.status.in_(("pending_approval", "approved", "paid")))
        .group_by(Expense.status)
    ).all()
    out = OpportunityExpenses()
    for status, n, total in rows:
        out.count += n
        if status == "pending_approval":
            out.pending += int(total)
        else:
            out.approved += int(total)
    return out


def deal_profit(
    db: Session, opportunity_id: uuid.UUID, expenses: OpportunityExpenses
) -> OpportunityProfit | None:
    """按客户接受的报价算这单赚多少；还没成交时按最新一张没被拒的报价估算。没有报价返回 None。"""
    # quote_service 依赖本模块（推进阶段），放在函数里导入避免循环引用
    from app.crm.services.quote_service import estimated_commission

    quotes = db.scalars(
        select(Quote)
        .where(Quote.opportunity_id == opportunity_id, Quote.status != "rejected")
        .order_by(Quote.created_at.desc())
    ).all()
    if not quotes:
        return None
    accepted = next((q for q in quotes if q.status == "accepted"), None)
    quote = accepted or quotes[0]
    gross = quote.total_price - quote.total_cost
    commission = estimated_commission(db, quote)
    spent = expenses.approved + expenses.pending
    return OpportunityProfit(
        quote_id=quote.id,
        quote_code=quote.code,
        basis="accepted" if accepted else "latest",
        price=quote.total_price,
        gross=gross,
        commission=commission,
        expenses=spent,
        net=gross - commission - spent,
    )


def get_detail(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> OpportunityDetail:
    item = get_item(db, user, opportunity_id)
    expenses = expense_summary(db, opportunity_id)
    return OpportunityDetail(
        **item.model_dump(),
        quotes=quote_query.list_for_opportunity(db, user, opportunity_id),
        activities=activity_service.list_for_subject(db, opportunity_id),
        expenses=expenses,
        profit=deal_profit(db, opportunity_id, expenses),
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
    ensure_owner(db.get(Customer, data.customer_id), user)  # 只能在自己负责的客户下建商机
    _check_product_line(db, data.product_line_id)
    opp = Opportunity(**data.model_dump(), stage="lead", owner_id=user.id, team_id=user.team_id)
    opp.name = data.name.strip()
    db.add(opp)
    db.flush()
    activity_service.record(db, user, "opportunity", opp.id, "create", opp.name, subject=opp)
    return get_item(db, user, opp.id)


def update_opportunity(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID, data: OpportunityUpdate
) -> OpportunityItem:
    opp = get_owned(db, user, opportunity_id)
    changes = data.model_dump(exclude_unset=True)
    if "product_line_id" in changes:
        _check_product_line(db, changes["product_line_id"])
    amount = changes.get("amount")
    if amount is not None and amount != opp.amount and _signed(db, opp):
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "已签合同的商机，金额按合同金额计，不能手动修改",
            {"rule": RULE_AMOUNT_SIGNED},
        )
    for key, value in changes.items():
        if value is None and key in {"name", "amount", "win_rate"}:
            continue  # 非空字段传 null 视为不修改
        setattr(opp, key, value.strip() if key == "name" else value)
    if changes:
        activity_service.record(
            db, user, "opportunity", opp.id, "update", _describe(changes), subject=opp
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
    return "、".join(labels.get(k, k) for k in changes)


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
    opp.win_rate = default_win_rate(change.stage, load_rules())  # 阶段默认赢率（rules.yaml）
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
    if change.stage == "won":
        _push_won(db, opp)


def _push_won(db: Session, opp: Opportunity) -> None:
    customer = db.get(Customer, opp.customer_id)
    owner = db.get(User, opp.owner_id) if opp.owner_id else None
    wecom_service.queue(
        db,
        "deal_won",
        f"赢单：{opp.name}",
        f"**🎉 赢单喜报**\n"
        f"> 客户：{customer.name if customer else '—'}\n"
        f"> 商机：{opp.name}\n"
        f'> 金额：<font color="info">¥{opp.amount / 100:,.0f}</font>\n'
        f"> 负责人：{owner.name if owner else '—'}",
    )


def change_stage(
    db: Session,
    user: CurrentUser,
    opportunity_id: uuid.UUID,
    change: StageChange,
    source: str = "manual",
) -> OpportunityItem:
    opp = get_owned(db, user, opportunity_id)
    if change.quote_id is not None:
        from app.crm.services import quote_win  # quote_win 依赖本模块，延迟导入

        quote_win.win_with_quote(db, user, opp, change.quote_id, source)
    else:
        if change.stage == "won" and opp.stage not in FINAL_STAGES:
            won_rule.reject_won_without_quote(db, opp)
        apply_stage(db, user, opp, change, source)
    return get_item(db, user, opp.id)


def _stage_rows(db: Session, user: CurrentUser, view: View | None) -> list[Any]:
    stmt = select(
        Opportunity.stage,
        func.count(),
        func.coalesce(func.sum(Opportunity.amount), 0),
    ).group_by(Opportunity.stage)
    return list(db.execute(apply_scope(stmt, Opportunity, user, view)).all())


RULE_AMOUNT_SIGNED = "opportunity_amount_signed"


def _signed(db: Session, opp: Opportunity) -> bool:
    return bool(db.scalar(select(_has_contract().where(Opportunity.id == opp.id))))


def _has_contract() -> Any:
    return exists().where(Contract.quote_id == Quote.id, Quote.opportunity_id == Opportunity.id)


def funnel(db: Session, user: CurrentUser, view: View | None = None) -> list[PipelineStage]:
    """各阶段数量和金额；赢单另外给出「还没有合同」的部分（手工标赢单、没走报价成交），
    这部分不计入工作台「本月成交」（成交按合同算），在漏斗上单独提示。"""
    counts = {stage: (int(c), int(a)) for stage, c, a in _stage_rows(db, user, view)}
    unsigned = select(func.count(), func.coalesce(func.sum(Opportunity.amount), 0)).where(
        Opportunity.stage == "won", ~_has_contract()
    )
    u_count, u_amount = db.execute(apply_scope(unsigned, Opportunity, user, view)).one()
    return [
        PipelineStage(
            stage=s,
            count=counts.get(s, (0, 0))[0],
            amount=counts.get(s, (0, 0))[1],
            unsigned_count=int(u_count) if s == "won" else 0,
            unsigned_amount=int(u_amount) if s == "won" else 0,
        )
        for s in STAGES
    ]


def sync_signed_amount(db: Session, user: CurrentUser, opp: Opportunity, source: str) -> None:
    """生成合同后商机金额改成已签合同金额合计：赢单金额 = 实际签约，漏斗和工作台成交对得上。"""
    signed = db.scalar(
        select(func.coalesce(func.sum(Contract.amount), 0))
        .join(Quote, Quote.id == Contract.quote_id)
        .where(Quote.opportunity_id == opp.id)
    )
    if not signed or signed == opp.amount:
        return
    content = f"商机金额按已签合同更新：¥{opp.amount / 100:,.0f} → ¥{signed / 100:,.0f}"
    opp.amount = int(signed)
    db.flush()
    activity_service.record(db, user, "opportunity", opp.id, "update", content, source, opp)


def pipeline_summary(db: Session, user: CurrentUser, view: View | None = None) -> PipelineSummary:
    """漏斗 + 合计：total / weighted / open_count 只算进行中的商机（不含赢单、输单）。"""
    stages = funnel(db, user, view)
    stmt = apply_scope(
        select(Opportunity.amount, Opportunity.win_rate).where(
            Opportunity.stage.not_in(FINAL_STAGES)
        ),
        Opportunity,
        user,
        view,
    )
    pairs = [(int(a), int(w)) for a, w in db.execute(stmt).all()]
    return PipelineSummary(
        stages=stages,
        total_amount=sum(a for a, _ in pairs),
        weighted_amount=weighted_amount(pairs),
        open_count=len(pairs),
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
