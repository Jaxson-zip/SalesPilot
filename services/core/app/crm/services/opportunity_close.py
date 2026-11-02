"""商机进入终态后的收尾：赢单推喜报；输单关闭未成交的报价、待审批和未完成的待办。

输单后不应再有「报价已审批，还没发给客户」「跟进报价」这类推进提醒：
- 草稿 / 待审批 / 已审批 / 已发送的报价改为「已关闭」，待审批的审批单一并驳回；
- 商机下未完成的待办（含发送报价时自动建的跟进任务）自动完成，备注写明原因。
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.models import Approval, Customer, Opportunity, Quote, Task, User
from app.crm.services import activity_service, quote_followups, wecom_service

OPEN_QUOTES = ("draft", "pending_approval", "approved", "sent")
LOST_NOTE = "商机已输单，自动关闭"


def push_won(db: Session, opp: Opportunity) -> None:
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


def _close_approvals(db: Session, quote: Quote, now: datetime) -> None:
    stmt = select(Approval).where(
        Approval.target_type == "quote",
        Approval.target_id == quote.id,
        Approval.status == "pending",
    )
    for a in db.scalars(stmt):
        a.status, a.comment, a.decided_at = "rejected", LOST_NOTE, now


def close_lost(db: Session, user: CurrentUser, opp: Opportunity) -> str:
    """关闭输单商机下未成交的报价和未完成的待办，返回追加到阶段动态里的说明。"""
    now = datetime.now(UTC)
    quotes = db.scalars(
        select(Quote).where(Quote.opportunity_id == opp.id, Quote.status.in_(OPEN_QUOTES))
    ).all()
    for q in quotes:
        _close_approvals(db, q, now)
        q.status = "closed"
        quote_followups.close_followups(db, q, "商机已输单")
        activity_service.record(db, user, "quote", q.id, "close", LOST_NOTE, subject=q)
    tasks = db.scalars(
        select(Task).where(
            Task.subject_type == "opportunity", Task.subject_id == opp.id, Task.done.is_(False)
        )
    ).all()
    for t in tasks:
        t.done, t.done_at = True, now
        t.note = "\n".join(filter(None, [t.note, LOST_NOTE]))
    parts = [f"关闭报价 {len(quotes)} 张"] if quotes else []
    parts += [f"完成待办 {len(tasks)} 条"] if tasks else []
    return f"；{'、'.join(parts)}" if parts else ""
