"""关闭还没成交的报价和未完成的待办：输单、赢单（同商机的其他报价）、退回公海、被新版本替代共用。

关闭一张报价 = 状态改「已关闭」、待审批的审批单驳回、发送时建的跟进任务完成、留一条动态。
客户手里的分享链接仍能打开，但页面显示「已失效」（share_service.public_quote）。
没有操作人（定时任务退回公海）时动态记为系统操作。
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.models import Approval, Quote, Task
from app.crm.services import activity_service, notification_service, quote_followups

OPEN_QUOTES = ("draft", "pending_approval", "approved", "sent")


def _reject_approvals(db: Session, quote: Quote, note: str, now: datetime) -> None:
    stmt = select(Approval).where(
        Approval.target_type == "quote",
        Approval.target_id == quote.id,
        Approval.status == "pending",
    )
    for a in db.scalars(stmt):
        a.status, a.comment, a.decided_at = "rejected", note, now
        notification_service.resolve_approval(db, a.id)


def close_quote(
    db: Session, user: CurrentUser | None, quote: Quote, note: str, reason: str
) -> None:
    """note 写进审批意见和动态；reason 写进自动完成的跟进任务备注。"""
    _reject_approvals(db, quote, note, datetime.now(UTC))
    quote.status = "closed"
    quote_followups.close_followups(db, quote, reason)
    if user is None:
        activity_service.record_system(
            db, "quote", quote.id, "close", note, quote.team_id, quote.owner_id
        )
    else:
        activity_service.record(db, user, "quote", quote.id, "close", note, subject=quote)


def close_open_quotes(
    db: Session, user: CurrentUser | None, where: Any, note: str, reason: str
) -> int:
    """关闭满足 where 的未成交报价，返回关闭的张数。"""
    stmt = select(Quote).where(where, Quote.status.in_(OPEN_QUOTES)).with_for_update()
    quotes = list(db.scalars(stmt).all())
    for q in quotes:
        close_quote(db, user, q, note, reason)
    return len(quotes)


def complete_tasks(db: Session, where: Any, note: str) -> int:
    """把满足 where 的未完成待办标为完成，备注写明原因；返回条数。"""
    tasks = list(db.scalars(select(Task).where(where, Task.done.is_(False))).all())
    now = datetime.now(UTC)
    for t in tasks:
        t.done, t.done_at = True, now
        t.note = "\n".join(filter(None, [t.note, note]))
    notification_service.resolve_tasks(db, [t.id for t in tasks])
    return len(tasks)


def summary(quotes: int, tasks: int) -> str:
    """追加到动态里的说明：「；关闭报价 N 张、完成待办 M 条」，都为 0 时为空串。"""
    parts = [f"关闭报价 {quotes} 张"] if quotes else []
    parts += [f"完成待办 {tasks} 条"] if tasks else []
    return f"；{'、'.join(parts)}" if parts else ""
