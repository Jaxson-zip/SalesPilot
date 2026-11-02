"""报价审批后的修改路径，以及草稿补关联客户。

- 撤回修改（revise）：已审批、还没发给客户的报价退回草稿，改完重新提交审批；
- 复制为新版本（copy_revision）：已发送 / 客户拒绝的报价复制成新草稿，记下 revision_of_id；
  新版本发送给客户后，原报价关闭（supersede），客户手里只有一份有效报价；
- 补关联（link）：AI 没识别出客户的草稿，选客户或商机后就能提交，明细和价格不动。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer, ensure_owner
from app.crm.models import Customer, Opportunity, Quote, QuoteItem
from app.crm.schemas.opportunity import StageChange
from app.crm.schemas.quote import QuoteLink, QuoteRef
from app.crm.services import activity_service, quote_followups, quote_validity
from app.crm.services.codes import next_code
from app.crm.services.opportunity_service import apply_stage

BEFORE_PROPOSAL = ("lead", "qualified")  # 出了报价单还停在这些阶段的商机推进到「方案报价」

RULE_REVISE = "quote_revise_not_allowed"
RULE_LINK = "quote_link_not_allowed"
COPYABLE = ("sent", "rejected")
OPEN = ("draft", "pending_approval", "approved")


def _deny(rule: str, message: str, quote: Quote) -> BizError:
    return BizError(ErrorCode.RULE_VIOLATION, message, {"rule": rule, "status": quote.status})


def revise(quote: Quote) -> str:
    """已审批未发送 → 草稿（清掉固化的范围、条款和有效期），返回动态说明。"""
    if quote.status != "approved":
        raise _deny(RULE_REVISE, "只有已审批、还没发给客户的报价可以撤回修改", quote)
    quote.status = "draft"
    quote.snapshot = None
    return "撤回修改：退回草稿，改完需要重新提交审批"


def _open_revision(db: Session, quote: Quote) -> Quote | None:
    stmt = select(Quote).where(Quote.revision_of_id == quote.id, Quote.status.in_(OPEN))
    return db.scalars(stmt.limit(1)).first()


def copy_revision(db: Session, user: CurrentUser, quote_id: uuid.UUID) -> uuid.UUID:
    """已发送 / 客户拒绝的报价复制为新草稿；已有没完成的新版本时不重复复制。"""
    ensure_business_writer(user)
    quote = db.get(Quote, quote_id, with_for_update=True)
    ensure_owner(quote, user)
    assert quote is not None
    if quote.status not in COPYABLE:
        raise _deny(RULE_REVISE, "已发送或客户拒绝的报价才能复制为新版本", quote)
    quote_validity.ensure_deal_open(db, quote.opportunity_id, "复制新版本")
    if found := _open_revision(db, quote):
        raise _deny(RULE_REVISE, f"已经有修订中的新版本 {found.code}，请在那张上继续改", quote)
    new = Quote(
        code=next_code(db, Quote.code, "Q"),
        **{k: getattr(quote, k) for k in ("opportunity_id", "customer_id", "pack", "tier")},
        **{k: getattr(quote, k) for k in ("total_cost", "total_price", "margin_rate")},
        discount_rate=quote.discount_rate,
        client_costs=list(quote.client_costs or []),
        status="draft",
        source="manual",
        revision_of_id=quote.id,
        owner_id=user.id,
        team_id=user.team_id,
    )
    db.add(new)
    db.flush()
    items = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id)).all()
    cols = ("sku", "name", "unit", "qty", "unit_cost", "unit_price", "category")
    db.add_all(QuoteItem(quote_id=new.id, **{c: getattr(i, c) for c in cols}) for i in items)
    db.flush()
    msg = f"复制 {quote.code} 为新版本 {new.code}"
    activity_service.record(db, user, "quote", new.id, "revision", msg, subject=new)
    return new.id


def supersede(db: Session, user: CurrentUser, quote: Quote) -> str:
    """新版本发给客户后关闭原报价（还在已审批 / 已发送的），返回追加到动态的说明。"""
    old = db.get(Quote, quote.revision_of_id) if quote.revision_of_id else None
    if old is None or old.status not in ("approved", "sent"):
        return ""
    old.status = "closed"
    quote_followups.close_followups(db, old, f"已被新版本 {quote.code} 替代")
    msg = f"已被新版本 {quote.code} 替代，报价关闭"
    activity_service.record(db, user, "quote", old.id, "close", msg, subject=old)
    return f"，原报价 {old.code} 已关闭"


def refs(db: Session, quote: Quote) -> dict[str, QuoteRef | list[QuoteRef] | None]:
    def ref(q: Quote) -> QuoteRef:
        return QuoteRef(id=q.id, code=q.code, status=q.status)  # type: ignore[arg-type]

    origin = db.get(Quote, quote.revision_of_id) if quote.revision_of_id else None
    stmt = select(Quote).where(Quote.revision_of_id == quote.id).order_by(Quote.created_at.desc())
    newer = [ref(q) for q in db.scalars(stmt)]
    return {"revision_of": ref(origin) if origin else None, "revisions": newer}


def link(db: Session, user: CurrentUser, quote_id: uuid.UUID, data: QuoteLink) -> None:
    """草稿补关联客户 / 商机（明细和价格不动）。"""
    quote = db.get(Quote, quote_id, with_for_update=True)
    ensure_owner(quote, user)
    assert quote is not None
    if quote.status != "draft":
        raise _deny(RULE_LINK, "只有草稿报价可以修改关联的客户和商机", quote)
    if data.opportunity_id is not None:
        opp = db.get(Opportunity, data.opportunity_id)
        ensure_owner(opp, user)  # 只能关联自己负责的商机
        assert opp is not None
        quote_validity.ensure_deal_open(db, opp.id, "关联报价")
        quote.opportunity_id, quote.customer_id = opp.id, opp.customer_id
        if opp.stage in BEFORE_PROPOSAL:
            apply_stage(db, user, opp, StageChange(stage="proposal"))
    elif data.customer_id is not None:
        ensure_owner(db.get(Customer, data.customer_id), user)
        quote.opportunity_id, quote.customer_id = None, data.customer_id
    else:
        raise BizError(ErrorCode.VALIDATION, "请选择客户或商机")
    customer = db.get(Customer, quote.customer_id)
    msg = f"关联客户「{customer.name if customer else '—'}」"
    activity_service.record(db, user, "quote", quote.id, "link", msg, subject=quote)
