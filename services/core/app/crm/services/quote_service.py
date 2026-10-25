"""报价单 service。

已实现：create_from_tier（Agent generate_quote 用，带幂等键）。
TODO: list / get / submit（pending_approval）/ send / accept（自动生成合同）/ reject。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.crm.models import Quote, QuoteItem
from app.crm.schemas.quote import QuoteItemOut, QuoteOut
from app.crm.services import activity_service
from app.crm.services.opportunity_service import get_opportunity
from app.packs.base import SolutionTier
from app.packs.registry import get_pack
from app.rules import check_margin, load_rules


def _next_code(db: Session) -> str:
    year = datetime.now(UTC).year
    count = db.scalar(select(func.count()).select_from(Quote)) or 0
    return f"Q-{year}-{count + 1:03d}"


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
    items = list(db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id)))
    return _to_out(quote, items)


def create_from_tier(
    db: Session,
    user: CurrentUser,
    *,
    pack: str,
    tier: SolutionTier,
    opportunity_id: uuid.UUID | None,
    idempotency_key: str,
) -> QuoteOut:
    """按方案档位生成报价单；同一幂等键重复调用返回同一张报价单。毛利由规则代码重新计算。"""
    if found := _existing(db, idempotency_key):
        return found
    opp = get_opportunity(db, user, opportunity_id) if opportunity_id else None
    total_cost = sum(i.unit_cost * i.qty for i in tier.items)
    margin = check_margin(total_cost, tier.total_price, load_rules(get_pack(pack).rules_file))
    quote = Quote(
        code=_next_code(db),
        opportunity_id=opp.id if opp else None,
        customer_id=opp.customer_id if opp else None,
        pack=pack,
        tier=tier.tier,
        status="draft" if margin.passed else "pending_approval",
        total_cost=total_cost,
        total_price=tier.total_price,
        margin_rate=margin.margin_rate,
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
        db, user, "quote", quote.id, "create", f"生成报价单 {quote.code}", "agent"
    )
    # TODO: 毛利不达标时创建 approval 记录（approval_service.create_for_quote）
    return _to_out(quote, items)


def get_quote(db: Session, user: CurrentUser, quote_id: uuid.UUID) -> QuoteOut:
    raise BizError(ErrorCode.NOT_IMPLEMENTED, "未实现")
