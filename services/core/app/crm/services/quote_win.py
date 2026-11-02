"""商机看板标赢单时按报价成交（opportunity_service 推进到赢单时调用）。"""

import uuid

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.crm.models import Opportunity, Quote
from app.crm.schemas.opportunity import FINAL_STAGES, StageChange
from app.crm.schemas.quote import QUOTE_STATUS_LABELS
from app.crm.services import activity_service, quote_service, won_rule
from app.crm.services.opportunity_service import apply_stage

WIN_STATUSES = won_rule.WIN_STATUSES
RULE_WIN_QUOTE = "won_quote_invalid"


def win_with_quote(
    db: Session, user: CurrentUser, opp: Opportunity, quote_id: uuid.UUID, source: str
) -> None:
    """商机看板标赢单时按报价成交：已审批未发送的先记一次发送，再走「客户接受」生成合同。"""
    if opp.stage in FINAL_STAGES:
        apply_stage(db, user, opp, StageChange(stage="won"), source)  # 抛出「已是终态」
    quote = db.get(Quote, quote_id, with_for_update=True)
    if quote is None or quote.opportunity_id != opp.id:
        raise BizError(ErrorCode.NOT_FOUND, "报价单不存在或不属于这个商机")
    ensure_owner(quote, user)
    if quote.status not in WIN_STATUSES:
        current = QUOTE_STATUS_LABELS.get(quote.status, quote.status)
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报价单 {quote.code} 当前为「{current}」，只有已审批或已发送的报价才能直接成交",
            {"rule": RULE_WIN_QUOTE, "status": quote.status},
        )
    if quote.status == "approved":
        quote.status = "sent"
        activity_service.record(
            db, user, "quote", quote.id, "send", "赢单时视为已发送", source, quote
        )
    content = quote_service.accept(db, user, quote, source)
    db.flush()
    activity_service.record(db, user, "quote", quote.id, "accept", content, source, quote)
