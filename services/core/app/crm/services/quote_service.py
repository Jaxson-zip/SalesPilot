"""报价单 service（接口契约 §3）：Agent 生成、列表 / 详情、submit / send / accept / reject 状态机。

accept 时自动生成合同（C-YYYY-NNN）和提成，并把关联商机改为赢单。
毛利、折扣、提成全部由 app.rules 计算，阈值来自 rules.yaml（含行业包覆盖）。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer, ensure_owner
from app.common.scope import View, ensure_visible
from app.crm.models import Commission, Contract, Customer, Opportunity, Quote, QuoteItem
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.opportunity import FINAL_STAGES, StageChange
from app.crm.schemas.quote import (
    QUOTE_STATUS_LABELS,
    QuoteDetail,
    QuoteItemOut,
    QuoteListItem,
    QuoteOut,
)
from app.crm.services import activity_service, approval_service, contract_service, quote_query
from app.crm.services.codes import next_code
from app.crm.services.opportunity_service import apply_stage, get_owned
from app.packs.base import SolutionTier
from app.packs.registry import get_pack
from app.rules import (
    CommissionLine,
    RuleSet,
    allocate_by_category,
    calc_commission,
    check_discount,
    check_margin,
    load_rules,
)
from app.rules.crm_calc import discount_rate_of, quote_valid_until

RULE_TRANSITION = "quote_status_transition"
# 动作 → (允许的当前状态, 结果状态)；submit 的结果由规则决定
TRANSITIONS: dict[str, tuple[str, str]] = {
    "submit": ("draft", "approved"),
    "send": ("approved", "sent"),
    "accept": ("sent", "accepted"),
    "reject": ("sent", "rejected"),
}
RULE_NO_CUSTOMER = "quote_no_customer"
ACTION_LABELS = {"submit": "提交", "send": "发送客户", "accept": "客户接受", "reject": "客户拒绝"}


def rules_for(quote: Quote) -> RuleSet:
    return load_rules(get_pack(quote.pack).rules_file)


def _to_out(quote: Quote, items: list[QuoteItem]) -> QuoteOut:
    return QuoteOut(
        id=quote.id,
        code=quote.code,
        opportunity_id=quote.opportunity_id,
        pack=quote.pack,
        tier=quote.tier,
        status=quote.status,  # type: ignore[arg-type]
        total_cost=quote.total_cost,
        total_price=quote.total_price,
        margin_rate=quote.margin_rate,
        items=[QuoteItemOut.model_validate(i, from_attributes=True) for i in items],
    )


def _existing(db: Session, key: str) -> QuoteOut | None:
    quote = db.scalar(select(Quote).where(Quote.idempotency_key == key))
    if quote is None:
        return None
    return _to_out(quote, quote_query.items_of(db, quote.id))


def create_from_tier(
    db: Session,
    user: CurrentUser,
    *,
    pack: str,
    tier: SolutionTier,
    opportunity_id: uuid.UUID | None,
    idempotency_key: str,
    customer_id: uuid.UUID | None = None,
) -> QuoteOut:
    """按方案档位生成草稿报价单；同一幂等键重复调用返回同一张。毛利由规则代码重新计算。

    是否需要审批在 submit 时按规则判定（接口契约 §3），这里一律是 draft。
    """
    ensure_business_writer(user)
    if found := _existing(db, idempotency_key):
        return found
    opp = get_owned(db, user, opportunity_id) if opportunity_id else None
    if opp is None and customer_id is not None:
        ensure_owner(db.get(Customer, customer_id), user)  # 只能给自己负责的客户出报价
    total_cost = sum(i.unit_cost * i.qty for i in tier.items)
    margin = check_margin(total_cost, tier.total_price, load_rules(get_pack(pack).rules_file))
    quote = Quote(
        code=next_code(db, Quote.code, "Q"),
        opportunity_id=opp.id if opp else None,
        customer_id=opp.customer_id if opp else customer_id,
        pack=pack,
        tier=tier.tier,
        status="draft",
        total_cost=total_cost,
        total_price=tier.total_price,
        margin_rate=margin.margin_rate,
        discount_rate=discount_rate_of(sum(i.total_price for i in tier.items), tier.total_price),
        idempotency_key=idempotency_key,
        source="agent",
        owner_id=user.id,
        team_id=user.team_id,
    )
    db.add(quote)
    db.flush()
    items = [QuoteItem(quote_id=quote.id, **i.model_dump()) for i in tier.items]
    db.add_all(items)
    db.flush()
    activity_service.record(
        db, user, "quote", quote.id, "create", f"生成报价单 {quote.code}", "agent", quote
    )
    return _to_out(quote, items)


def list_quotes(
    db: Session,
    user: CurrentUser,
    view: View | None,
    page: PageParams,
    status: str | None = None,
    opportunity_id: uuid.UUID | None = None,
    q: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> Page[QuoteListItem]:
    base = quote_query.build_query(user, view, status, opportunity_id, q, customer_id)
    total = quote_query.count(db, base)
    stmt = base.order_by(Quote.created_at.desc(), Quote.id).offset(page.offset)
    quotes = list(db.scalars(stmt.limit(page.page_size)).all())
    return Page[QuoteListItem](items=quote_query.to_items(db, quotes), total=total)


def _load(db: Session, user: CurrentUser, quote_id: uuid.UUID, lock: bool = False) -> Quote:
    quote = db.get(Quote, quote_id, with_for_update=lock)
    ensure_visible(quote, user)
    assert quote is not None
    return quote


def commission_lines(items: list[QuoteItem], total_price: int) -> list[CommissionLine]:
    return allocate_by_category([(i.category, i.unit_price * i.qty) for i in items], total_price)


def _contract_of(db: Session, quote_id: uuid.UUID) -> Contract | None:
    return db.scalar(select(Contract).where(Contract.quote_id == quote_id))


def _estimated_commission(db: Session, quote: Quote, contract: Contract | None) -> int:
    if contract is not None:
        stmt = select(Commission.estimated).where(Commission.contract_id == contract.id)
        return int(sum(db.scalars(stmt).all()))
    lines = commission_lines(quote_query.items_of(db, quote.id), quote.total_price)
    return calc_commission(lines, quote.margin_rate, 0.0, rules_for(quote)).estimated


def get_quote(db: Session, user: CurrentUser, quote_id: uuid.UUID) -> QuoteDetail:
    db.flush()
    quote = _load(db, user, quote_id)
    db.refresh(quote)
    contract = _contract_of(db, quote.id)
    lines = quote_query.to_lines(quote_query.items_of(db, quote.id))
    return QuoteDetail(
        **quote_query.to_items(db, [quote])[0].model_dump(),
        items=lines,
        approvals=quote_query.approvals_of(db, "quote", quote.id),
        contract_id=contract.id if contract else None,
        estimated_commission=_estimated_commission(db, quote, contract),
        list_price=sum(i.subtotal_price for i in lines),
        discount_rate=quote.discount_rate,
        valid_until=quote_valid_until(quote.created_at, rules_for(quote)),
    )


def _check_transition(quote: Quote, action: str) -> None:
    allowed, _ = TRANSITIONS[action]
    if quote.status != allowed:
        current = QUOTE_STATUS_LABELS.get(quote.status, quote.status)
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报价单当前为「{current}」，不能{ACTION_LABELS[action]}",
            {"rule": RULE_TRANSITION, "status": quote.status, "action": action},
        )


def approval_reasons(quote: Quote, items: list[QuoteItem], rules: RuleSet) -> list[str]:
    """返回触发审批的规则说明；空列表表示无需审批。"""
    reasons: list[str] = []
    margin = check_margin(quote.total_cost, quote.total_price, rules)
    if not margin.passed:
        reasons.append(margin.reason)
    list_price = sum(i.unit_price * i.qty for i in items)
    if list_price > 0 and not check_discount(list_price, quote.total_price, rules):
        discount = (list_price - quote.total_price) / list_price
        reasons.append(f"折扣 {discount:.1%} 超出销售权限 {rules.discount.max_rate:.0%}")
    return reasons


def _suggestion(reasons: list[str]) -> str:
    return "；".join(reasons) + "。建议核对配置与成本，确认客户战略价值后再决定是否通过。"


def _submit(db: Session, user: CurrentUser, quote: Quote) -> str:
    items = quote_query.items_of(db, quote.id)
    reasons = approval_reasons(quote, items, rules_for(quote))
    if not reasons:
        quote.status = "approved"
        return "提交报价单，规则校验通过，自动审批"
    quote.status = "pending_approval"
    approval_service.create_approval(db, "quote", quote, "；".join(reasons), _suggestion(reasons))
    return "提交报价单，进入主管审批：" + "；".join(reasons)


def _accept(db: Session, user: CurrentUser, quote: Quote, source: str) -> str:
    quote.status = "accepted"
    contract = Contract(
        code=next_code(db, Contract.code, "C"),
        quote_id=quote.id,
        customer_id=quote.customer_id,
        amount=quote.total_price,
        paid_amount=0,
        status="active",
        owner_id=quote.owner_id,
        team_id=quote.team_id,
    )
    db.add(contract)
    db.flush()
    lines = commission_lines(quote_query.items_of(db, quote.id), quote.total_price)
    result = calc_commission(lines, quote.margin_rate, 0.0, rules_for(quote))
    db.add(
        Commission(
            contract_id=contract.id,
            user_id=quote.owner_id or user.id,
            estimated=result.estimated,
            confirmed=0,
            owner_id=quote.owner_id,
            team_id=quote.team_id,
        )
    )
    contract_service.create_default_plan(db, contract, rules_for(quote))
    _mark_won(db, user, quote.opportunity_id, source)
    return f"客户接受报价，生成合同 {contract.code}"


def _mark_won(db: Session, user: CurrentUser, opportunity_id: uuid.UUID | None, src: str) -> None:
    if opportunity_id is None:
        return
    opp = db.get(Opportunity, opportunity_id)
    if opp is not None and opp.stage not in FINAL_STAGES:
        apply_stage(db, user, opp, StageChange(stage="won"), src)


def transition(
    db: Session, user: CurrentUser, quote_id: uuid.UUID, action: str, source: str = "manual"
) -> QuoteDetail:
    """报价单状态流转：非法流转一律 42201 rule=quote_status_transition。"""
    if action not in TRANSITIONS:
        raise BizError(ErrorCode.VALIDATION, f"未知动作：{action}")
    quote = db.get(Quote, quote_id, with_for_update=True)
    ensure_owner(quote, user)  # 提交 / 发送 / 接受 / 拒绝：只有负责人本人
    assert quote is not None
    _check_transition(quote, action)
    if action == "submit" and quote.customer_id is None:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "报价单还没有关联客户：请从商机侧栏点「出方案」，或在 AI 对话里写明客户名称后重新生成",
            {"rule": RULE_NO_CUSTOMER},
        )
    if action == "submit":
        content = _submit(db, user, quote)
    elif action == "accept":
        content = _accept(db, user, quote, source)
    else:
        quote.status = TRANSITIONS[action][1]
        content = f"报价单{ACTION_LABELS[action]}"
    db.flush()
    activity_service.record(db, user, "quote", quote.id, action, content, source, quote)
    return get_quote(db, user, quote.id)
