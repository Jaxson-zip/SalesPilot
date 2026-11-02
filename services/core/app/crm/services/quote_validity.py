"""报价有效期贯穿成交流程：过期的报价不能再发送、客户接受或按它赢单，要先续期。

有效期在提交审批时固化（quote_snapshot.valid_until_of）。续期 = 退回草稿：
销售重新确认价格和范围后再提交，按当天重新起算有效期，需要审批的照常走审批。
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.common.errors import BizError, ErrorCode
from app.crm.models import Opportunity, Quote
from app.crm.services import quote_snapshot
from app.crm.services.codes import local_today

RULE_EXPIRED = "quote_expired"
RULE_RENEW = "quote_renew_not_allowed"
RENEWABLE = ("approved", "sent")
RULE_DEAL_LOST = "opportunity_lost"


def is_expired(quote: Quote, today: date | None = None) -> bool:
    if quote.status in ("draft", "pending_approval"):
        return False  # 还没定稿：有效期提交时才定
    return quote_snapshot.valid_until_of(quote) < (today or local_today())


def ensure_valid(quote: Quote, doing: str) -> None:
    """发送、客户接受、按报价赢单前调用；过期抛 42201 rule=quote_expired。"""
    if not is_expired(quote):
        return
    until = quote_snapshot.valid_until_of(quote)
    raise BizError(
        ErrorCode.RULE_VIOLATION,
        f"报价单 {quote.code} 已过有效期（{until:%Y-%m-%d}），不能{doing}；"
        "请先「续期」重新确认价格后再提交",
        {"rule": RULE_EXPIRED, "valid_until": until.isoformat()},
    )


def renew(quote: Quote) -> str:
    """已过期的已审批 / 已发送报价退回草稿（清掉快照），返回动态说明。"""
    if quote.status not in RENEWABLE or not is_expired(quote):
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "只有已过有效期、还没成交的报价需要续期",
            {"rule": RULE_RENEW, "status": quote.status},
        )
    until = quote_snapshot.valid_until_of(quote)
    quote.status = "draft"
    quote.snapshot = None
    return f"报价已过有效期（{until:%Y-%m-%d}），退回草稿续期：确认价格后重新提交"


def ensure_deal_open(db: Session, opportunity_id: uuid.UUID | None, doing: str) -> None:
    """商机已输单：不能再出报价、提交、发送或成交（报价随输单关闭）。"""
    opp = db.get(Opportunity, opportunity_id) if opportunity_id else None
    if opp is None or opp.stage != "lost":
        return
    raise BizError(
        ErrorCode.RULE_VIOLATION,
        f"商机「{opp.name}」已输单，不能{doing}；客户重新有需求时请新建商机",
        {"rule": RULE_DEAL_LOST},
    )
