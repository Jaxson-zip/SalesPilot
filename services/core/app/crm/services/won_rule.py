"""赢单规则：商机只能按已审批 / 已发送的报价成交（生成合同、回款计划和提成）。

回归：原来看板和对话都能「只标记赢单」——发了赢单喜报，合同页却没有合同，也算不出提成。
现在没有指定报价时直接拒绝，并告诉用户可以按哪张报价成交，或者先去出报价。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.errors import BizError, ErrorCode
from app.crm.models import Opportunity, Quote

RULE_WON_NEEDS_QUOTE = "won_needs_quote"
# 能直接成交的报价状态（前端 WonDialog 的 WINNABLE 与此一致）
WIN_STATUSES = ("approved", "sent")


def winnable_quotes(db: Session, opp: Opportunity) -> list[dict[str, Any]]:
    """可成交的报价 [{id, code, status}]，新的在前；id 给 Agent 作为 quote_id 用。"""
    stmt = (
        select(Quote.id, Quote.code, Quote.status)
        .where(Quote.opportunity_id == opp.id, Quote.status.in_(WIN_STATUSES))
        .order_by(Quote.created_at.desc())
    )
    return [{"id": str(i), "code": c, "status": st} for i, c, st in db.execute(stmt)]


def reject_won_without_quote(db: Session, opp: Opportunity) -> None:
    """标赢单却没指定报价：抛 RULE_VIOLATION，提示按哪张报价成交或先出报价。"""
    quotes = winnable_quotes(db, opp)
    codes = [q["code"] for q in quotes]
    if codes:
        hint = f"请选择按报价 {'、'.join(codes)} 成交，会自动生成合同和回款计划"
    else:
        hint = "这个商机还没有已审批或已发送的报价，请先出报价并审批通过，客户接受后会自动赢单"
    raise BizError(
        ErrorCode.RULE_VIOLATION,
        f"赢单需要按报价成交：{hint}",
        {"rule": RULE_WON_NEEDS_QUOTE, "quotes": quotes},
    )
