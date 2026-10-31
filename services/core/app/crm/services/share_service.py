"""报价分享链接（接口契约 §35）：负责人生成只读链接发给甲方，甲方不用登录就能看报价。

- 只有已审批 / 已发送 / 已成交的报价能分享；已审批的生成链接时同时记为「已发送客户」
  （和点「发送」一样建跟进任务），前端在生成前弹确认。
- 链接有效期跟报价有效期走（rules.yaml quote.valid_days），过期或撤销后打开是 40401。
- 公开视图只给甲方该看的：明细单价、合计、折扣、客户自付费用、项目范围；不含成本、毛利、提成。
- 甲方每天第一次打开记一条动态并通知负责人（「客户在看报价」是跟进的好时机）。
"""

import secrets
import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.common.scope import ensure_visible
from app.crm.models import Customer, Opportunity, Quote, QuoteShare, User
from app.crm.schemas.quote import QUOTE_STATUS_LABELS, QuoteLine
from app.crm.schemas.share import PublicQuote, PublicQuoteLine, PublicScope, QuoteShareOut
from app.crm.services import (
    activity_service,
    notification_service,
    quote_query,
    quote_service,
    template_service,
)
from app.crm.services.codes import LOCAL_TZ
from app.packs.base import TIER_NAMES
from app.rules.crm_calc import local_date, quote_valid_until

SHAREABLE = ("approved", "sent", "accepted")
RULE_SHARE_STATUS = "quote_share_status"
RULE_SHARE_EXPIRED = "quote_share_expired"


def _now() -> datetime:
    return datetime.now(UTC)


def _active(db: Session, quote_id: uuid.UUID) -> QuoteShare | None:
    stmt = (
        select(QuoteShare)
        .where(
            QuoteShare.quote_id == quote_id,
            QuoteShare.revoked_at.is_(None),
            QuoteShare.expires_at > _now(),
        )
        .order_by(QuoteShare.created_at.desc())
    )
    return db.scalars(stmt).first()


def _to_out(share: QuoteShare) -> QuoteShareOut:
    return QuoteShareOut(
        token=share.token,
        path=f"/share/q/{share.token}",
        expires_at=share.expires_at,
        view_count=share.view_count,
        last_viewed_at=share.last_viewed_at,
        created_at=share.created_at,
    )


def _valid_until(quote: Quote) -> date:
    return quote_valid_until(quote.created_at, quote_service.rules_for(quote))


def _check_shareable(quote: Quote) -> datetime:
    """返回链接的过期时间：报价有效期最后一天的 24 点（北京时间）。"""
    if quote.status not in SHAREABLE:
        current = QUOTE_STATUS_LABELS.get(quote.status, quote.status)
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报价单当前为「{current}」，审批通过后才能分享给客户",
            {"rule": RULE_SHARE_STATUS, "status": quote.status},
        )
    last_day = _valid_until(quote)
    expires = datetime.combine(last_day + timedelta(days=1), time(0), tzinfo=LOCAL_TZ)
    if expires <= _now():
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报价已过有效期（{last_day:%Y-%m-%d}），请重新出一版报价",
            {"rule": RULE_SHARE_EXPIRED},
        )
    return expires


def create_share(db: Session, user: CurrentUser, quote_id: uuid.UUID) -> QuoteShareOut:
    """生成分享链接；已有有效链接直接返回（重复点不会生成多条）。"""
    quote = db.get(Quote, quote_id, with_for_update=True)
    ensure_owner(quote, user)
    assert quote is not None
    expires = _check_shareable(quote)
    if (existing := _active(db, quote.id)) is not None:
        return _to_out(existing)
    if quote.status == "approved":  # 发链接就是发给客户：和点「发送」一样记录并建跟进任务
        quote_service.transition(db, user, quote.id, "send")
    share = QuoteShare(
        quote_id=quote.id, token=secrets.token_urlsafe(24), expires_at=expires, created_by=user.id
    )
    db.add(share)
    db.flush()
    content = f"生成报价分享链接（{_valid_until(quote):%m-%d} 前有效）"
    activity_service.record(db, user, "quote", quote.id, "share", content, "manual", quote)
    return _to_out(share)


def get_share(db: Session, user: CurrentUser, quote_id: uuid.UUID) -> QuoteShareOut | None:
    ensure_visible(db.get(Quote, quote_id), user)
    share = _active(db, quote_id)
    return _to_out(share) if share else None


def revoke_share(db: Session, user: CurrentUser, quote_id: uuid.UUID) -> None:
    """撤销后甲方再打开就是「链接已失效」；没有有效链接时什么也不做。"""
    quote = db.get(Quote, quote_id)
    ensure_owner(quote, user)
    assert quote is not None
    share = _active(db, quote_id)
    if share is None:
        return
    share.revoked_at = _now()
    activity_service.record(
        db, user, "quote", quote.id, "share_revoked", "撤销报价分享链接", "manual", quote
    )


def _record_view(db: Session, share: QuoteShare, quote: Quote) -> None:
    """每天第一次打开记动态并通知负责人；之后只累加次数。"""
    now = _now()
    first_today = share.last_viewed_at is None or local_date(share.last_viewed_at) != local_date(
        now
    )
    share.view_count += 1
    share.last_viewed_at = now
    if not first_today:
        return
    customer = db.get(Customer, quote.customer_id) if quote.customer_id else None
    who = customer.name if customer else "客户"
    activity_service.record_system(
        db, "quote", quote.id, "viewed", f"{who}打开了报价分享链接", quote.team_id, quote.owner_id
    )
    notification_service.notify(
        db,
        [quote.owner_id],
        "quote_viewed",
        f"{who}正在看报价 {quote.code}",
        "客户打开了你发的报价链接，现在跟进正是时候",
        notification_service.subject_link("quote", quote.id),
    )


def _scope(opp: Opportunity | None, pack: str) -> PublicScope | None:
    """和打印版一致：只有商机上「已确认」且同一行业包的需求清单才给甲方看。"""
    req = (opp.requirement or {}) if opp else {}
    data = req.get("data")
    if not req.get("confirmed") or req.get("pack") != pack or not isinstance(data, dict):
        return None
    modules = [m["name"] for m in data.get("modules") or [] if isinstance(m, dict) and "name" in m]
    return PublicScope(
        platforms=list(data.get("platforms") or []),
        modules=modules,
        team_size=data.get("team_size"),
    )


def _name(db: Session, model: type[Customer] | type[User], key: uuid.UUID | None) -> str | None:
    row = db.get(model, key) if key else None
    return row.name if row else None


def _line(ln: QuoteLine) -> PublicQuoteLine:
    """逐个字段挑出来（不用 model_dump 透传），成本字段不会因为改 schema 漏给甲方。"""
    return PublicQuoteLine(
        name=ln.name,
        unit=ln.unit,
        qty=ln.qty,
        unit_price=ln.unit_price,
        subtotal_price=ln.subtotal_price,
        category=ln.category,
    )


def public_quote(db: Session, token: str, count_view: bool = True) -> PublicQuote:
    """甲方查看：链接不存在、已撤销、已过期都是 40401（不区分，避免猜测）。

    count_view=False：登录着的自己人在预览，不记打开次数、不提醒。"""
    share = db.scalar(select(QuoteShare).where(QuoteShare.token == token).with_for_update())
    if share is None or share.revoked_at is not None or share.expires_at <= _now():
        raise BizError(ErrorCode.NOT_FOUND, "链接已失效，请联系发送人重新获取")
    quote = db.get(Quote, share.quote_id)
    assert quote is not None
    if count_view:
        _record_view(db, share, quote)
    lines = quote_query.to_lines(quote_query.items_of(db, quote.id))
    opp = db.get(Opportunity, quote.opportunity_id) if quote.opportunity_id else None
    return PublicQuote(
        code=quote.code,
        status=quote.status,  # type: ignore[arg-type]
        customer_name=_name(db, Customer, quote.customer_id),
        opportunity_name=opp.name if opp else None,
        tier_name=TIER_NAMES.get(quote.tier, quote.tier),
        owner_name=_name(db, User, quote.owner_id),
        created_at=quote.created_at,
        valid_until=_valid_until(quote),
        items=[_line(ln) for ln in lines],
        list_price=sum(ln.subtotal_price for ln in lines),
        discount_rate=quote.discount_rate,
        total_price=quote.total_price,
        client_costs=quote.client_costs or [],
        scope=_scope(opp, quote.pack),
        terms=template_service.get_templates(Role.SALES).quote_terms,
    )
