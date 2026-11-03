"""任务 / 下一步行动 service（接口契约 v3 §12）。

权限（契约 §0）：只能给自己负责的客户 / 商机建任务；只有负责人本人能修改、完成、删除；
管理员只读（role_forbidden）；主管改销售的任务 → not_owner。数据范围与其他业务数据一致。
「今天 / 逾期」按北京时间自然日：到期日早于今天且未完成 = 逾期。
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.common.scope import View, apply_scope
from app.crm.models import Customer, Opportunity, Task
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.task import TaskCreate, TaskItem, TaskUpdate
from app.crm.services import activity_service, lookup, notification_service
from app.crm.services.quote_query import count
from app.rules.crm_calc import LOCAL_TZ, day_bounds, is_task_overdue

RULE_TASK_DONE = "task_done_not_deletable"


def as_aware(moment: datetime) -> datetime:
    """不带时区的时间按北京时间处理。"""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=LOCAL_TZ)


def _subject(db: Session, subject_type: str, subject_id: uuid.UUID) -> Customer | Opportunity:
    model: type[Customer] | type[Opportunity] = (
        Customer if subject_type == "customer" else Opportunity
    )
    obj = db.get(model, subject_id)
    if obj is None:
        raise BizError(ErrorCode.NOT_FOUND, "关联对象不存在")
    return obj


def to_items(db: Session, tasks: list[Task], now: datetime | None = None) -> list[TaskItem]:
    current = now or datetime.now(UTC)
    owners = lookup.users(db, (t.owner_id for t in tasks))
    customers = lookup.customers(db, (t.subject_id for t in tasks if t.subject_type == "customer"))
    opps = lookup.opportunities(
        db, (t.subject_id for t in tasks if t.subject_type == "opportunity")
    )
    names = {**{k: v.name for k, v in customers.items()}, **{k: v.name for k, v in opps.items()}}
    return [
        TaskItem(
            id=t.id,
            title=t.title,
            type=t.type,  # type: ignore[arg-type]
            due_at=t.due_at,
            done=t.done,
            done_at=t.done_at,
            note=t.note,
            subject_type=t.subject_type,  # type: ignore[arg-type]
            subject_id=t.subject_id,
            subject_name=names.get(t.subject_id),
            owner=lookup.pick(owners, t.owner_id),
            overdue=is_task_overdue(t.due_at, t.done, current),
        )
        for t in tasks
    ]


def apply_due(stmt: Select[Any], due: str | None, now: datetime) -> Select[Any]:
    """due=today 今天到期；overdue 到期日早于今天且未完成；week 今天起 7 天内到期。"""
    start, end = day_bounds(now)
    if due == "today":
        return stmt.where(Task.due_at >= start, Task.due_at < end)
    if due == "overdue":
        return stmt.where(Task.due_at < start, Task.done.is_(False))
    if due == "week":
        return stmt.where(Task.due_at >= start, Task.due_at < start + timedelta(days=7))
    return stmt


def list_tasks(
    db: Session,
    user: CurrentUser,
    view: View | None,
    page: PageParams,
    filters: dict[str, Any],
) -> Page[TaskItem]:
    """filters：status(open/done)、due(today/overdue/week)、subject_type、subject_id。"""
    stmt = apply_scope(select(Task), Task, user, view)
    if filters.get("status"):
        stmt = stmt.where(Task.done.is_(filters["status"] == "done"))
    if filters.get("subject_type"):
        stmt = stmt.where(Task.subject_type == filters["subject_type"])
    if filters.get("subject_id"):
        stmt = stmt.where(Task.subject_id == filters["subject_id"])
    stmt = apply_due(stmt, filters.get("due"), datetime.now(UTC))
    total = count(db, stmt)
    stmt = stmt.order_by(Task.done, Task.due_at, Task.id).offset(page.offset)
    rows = list(db.scalars(stmt.limit(page.page_size)).all())
    return Page[TaskItem](items=to_items(db, rows), total=total)


def create_task(
    db: Session, user: CurrentUser, data: TaskCreate, source: str = "manual"
) -> TaskItem:
    subject = _subject(db, data.subject_type, data.subject_id)
    ensure_owner(subject, user)  # 看不到 40401；管理员 role_forbidden；不是负责人 not_owner
    customer_id = subject.id if isinstance(subject, Customer) else subject.customer_id
    task = Task(
        **data.model_dump(exclude={"due_at", "title"}),
        title=data.title.strip(),
        due_at=as_aware(data.due_at),
        done=False,
        customer_id=customer_id,
        owner_id=subject.owner_id,
        team_id=subject.team_id,
    )
    db.add(task)
    db.flush()
    db.refresh(task)
    return to_items(db, [task])[0]


def _load_owned(db: Session, user: CurrentUser, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id, with_for_update=True)
    ensure_owner(task, user)
    assert task is not None
    return task


def _set_done(db: Session, user: CurrentUser, task: Task, done: bool, source: str) -> None:
    if done == task.done:
        return
    task.done = done
    task.done_at = datetime.now(UTC) if done else None
    if done:
        subject = _subject(db, task.subject_type, task.subject_id)
        activity_service.record(
            db, user, task.subject_type, task.subject_id, "task_done",
            f"完成任务：{task.title}", source, subject,
        )  # fmt: skip


def update_task(
    db: Session, user: CurrentUser, task_id: uuid.UUID, data: TaskUpdate, source: str = "manual"
) -> TaskItem:
    task = _load_owned(db, user, task_id)
    changes = data.model_dump(exclude_unset=True)
    for key in ("title", "type"):
        if changes.get(key) is not None:
            setattr(task, key, changes[key].strip() if key == "title" else changes[key])
    if changes.get("due_at") is not None:
        task.due_at = as_aware(changes["due_at"])
    if "note" in changes:
        task.note = changes["note"]
    if changes.get("done") is not None:
        _set_done(db, user, task, bool(changes["done"]), source)
    if task.done or changes.get("due_at") is not None:
        notification_service.resolve_tasks(db, [task.id])  # 完成 / 改期后旧的到期提醒失效
    db.flush()
    db.refresh(task)
    return to_items(db, [task])[0]


def delete_task(db: Session, user: CurrentUser, task_id: uuid.UUID) -> None:
    """只能删除未完成的任务（已完成的是历史记录）。"""
    task = _load_owned(db, user, task_id)
    if task.done:
        raise BizError(ErrorCode.RULE_VIOLATION, "已完成的任务不能删除", {"rule": RULE_TASK_DONE})
    notification_service.resolve_tasks(db, [task.id])
    db.delete(task)
    db.flush()


def count_due(db: Session, user: CurrentUser, view: View | None) -> dict[str, int]:
    """工作台：今天到期（未完成）与已逾期的任务数。"""
    now = datetime.now(UTC)
    base = apply_scope(select(Task).where(Task.done.is_(False)), Task, user, view)
    return {
        "tasks_today": count(db, apply_due(base, "today", now)),
        "tasks_overdue": count(db, apply_due(base, "overdue", now)),
    }
