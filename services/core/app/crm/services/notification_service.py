"""站内通知 service（接口契约 v3 §15）。

触发点：
- 提交审批 → 通知本团队主管（approval_pending）
- 审批通过 / 驳回 → 通知申请人（approval_decided）
- 客户被转移 → 通知新负责人（customer_assigned）
- 任务今天到期 → 查询通知时补生成（task_due），dedupe_key 保证同一任务同一天只生成一次

通知只属于接收人本人：列表和已读都按 user_id 过滤。
"""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.crm.models import Notification, Task, User
from app.crm.schemas.task import (
    NotificationItem,
    NotificationList,
    NotificationReadResult,
)
from app.rules.crm_calc import day_bounds, local_date

MAX_LIMIT = 100


def notify(
    db: Session,
    user_ids: Iterable[uuid.UUID | None],
    type_: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> int:
    """给一组用户各写一条通知（去重、忽略空 id），返回写入条数。"""
    targets = {u for u in user_ids if u is not None}
    for user_id in targets:
        db.add(Notification(user_id=user_id, type=type_, title=title, body=body, link=link))
    db.flush()
    return len(targets)


def notify_once(
    db: Session,
    user_id: uuid.UUID,
    type_: str,
    title: str,
    dedupe_key: str,
    body: str | None = None,
    link: str | None = None,
) -> bool:
    """按 dedupe_key 只写一次（定时任务重复运行、手动「立即运行」都不会重复提醒）；写入了返回 True。

    dedupe_key 全局唯一，同一件事提醒多个人时 key 里要带上接收人。"""
    values = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "type": type_,
        "title": title[:200],
        "body": body,
        "link": link,
        "read": False,
        "dedupe_key": dedupe_key[:150],
    }
    stmt = insert(Notification).values(**values).on_conflict_do_nothing()
    return db.scalar(stmt.returning(Notification.id)) is not None


def team_managers(db: Session, team_id: uuid.UUID | None) -> list[uuid.UUID]:
    if team_id is None:
        return []
    stmt = select(User.id).where(User.team_id == team_id, User.role == Role.MANAGER.value)
    return list(db.scalars(stmt).all())


def subject_link(subject_type: str, subject_id: uuid.UUID) -> str:
    """前端路由：商机在看板侧栏打开，报销在列表页打开，其余有详情页。"""
    if subject_type == "opportunity":
        return f"/pipeline?opportunity={subject_id}"
    if subject_type == "expense":
        return f"/expenses?id={subject_id}"
    if subject_type == "quote":
        return f"/quotes/{subject_id}"
    return f"/customers/{subject_id}"


def ensure_task_due(db: Session, user: CurrentUser, now: datetime | None = None) -> int:
    """为本人今天到期、未完成的任务补生成 task_due 通知（同一任务同一天只生成一次）。"""
    current = now or datetime.now(UTC)
    start, end = day_bounds(current)
    stmt = select(Task).where(
        Task.owner_id == user.id, Task.done.is_(False), Task.due_at >= start, Task.due_at < end
    )
    tasks = list(db.scalars(stmt).all())
    day = local_date(current).isoformat()
    for t in tasks:
        values = {
            "id": uuid.uuid4(),
            "user_id": user.id,
            "type": "task_due",
            "title": f"任务今天到期：{t.title}",
            "body": t.note,
            "link": subject_link(t.subject_type, t.subject_id),
            "read": False,
            "dedupe_key": f"task_due:{t.id}:{day}",
        }
        db.execute(insert(Notification).values(**values).on_conflict_do_nothing())
    db.flush()
    return len(tasks)


def _to_item(n: Notification) -> NotificationItem:
    return NotificationItem(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        link=n.link,
        read=n.read,
        created_at=n.created_at,
    )


def count_unread(db: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(Notification.user_id == user_id, Notification.read.is_(False))
    return db.scalar(stmt) or 0


def list_notifications(
    db: Session, user: CurrentUser, unread_only: bool = False, limit: int = 20
) -> NotificationList:
    ensure_task_due(db, user)
    where = [Notification.user_id == user.id]
    if unread_only:
        where.append(Notification.read.is_(False))
    total = db.scalar(select(func.count()).select_from(Notification).where(*where)) or 0
    stmt = (
        select(Notification)
        .where(*where)
        .order_by(Notification.created_at.desc(), Notification.id)
        .limit(min(limit, MAX_LIMIT))
    )
    items = [_to_item(n) for n in db.scalars(stmt).all()]
    return NotificationList(items=items, total=total, unread=count_unread(db, user.id))


def mark_read(
    db: Session, user: CurrentUser, ids: list[uuid.UUID] | None = None
) -> NotificationReadResult:
    """标记已读：不传 ids 表示全部；别人的通知 id 会被忽略。"""
    stmt = update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))
    if ids is not None:
        stmt = stmt.where(Notification.id.in_(ids))
    result = db.execute(stmt.values(read=True, read_at=datetime.now(UTC)))
    db.flush()
    updated = int(getattr(result, "rowcount", 0) or 0)
    return NotificationReadResult(updated=updated, unread=count_unread(db, user.id))
