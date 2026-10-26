"""商机列表 / 详情的派生字段（接口契约 v3 §12、§13）：下一步任务、最近动态时间、停滞判断。

批量查询，避免列表逐条查库。停滞的判断由 app.rules.crm_calc 的纯函数完成，阈值来自 rules.yaml。
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crm.models import Activity, Followup, Opportunity, Task
from app.crm.schemas.task import NextTask
from app.rules import RuleSet, load_rules
from app.rules.crm_calc import idle_days_of, is_stale, is_task_overdue


def next_tasks(db: Session, opp_ids: list[uuid.UUID], now: datetime) -> dict[uuid.UUID, NextTask]:
    """每个商机最早到期的未完成任务。"""
    if not opp_ids:
        return {}
    stmt = (
        select(Task)
        .where(
            Task.subject_type == "opportunity",
            Task.subject_id.in_(opp_ids),
            Task.done.is_(False),
        )
        .order_by(Task.subject_id, Task.due_at, Task.id)
    )
    found: dict[uuid.UUID, NextTask] = {}
    for t in db.scalars(stmt).all():
        if t.subject_id not in found:
            found[t.subject_id] = NextTask(
                id=t.id,
                title=t.title,
                due_at=t.due_at,
                overdue=is_task_overdue(t.due_at, False, now),
            )
    return found


def _latest_activities(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    stmt = (
        select(Activity.subject_id, func.max(Activity.created_at))
        .where(Activity.subject_id.in_(ids))
        .group_by(Activity.subject_id)
    )
    return {sid: at for sid, at in db.execute(stmt).all()}


def _latest_followups(db: Session, customer_ids: set[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    when = func.coalesce(Followup.occurred_at, Followup.created_at)
    stmt = (
        select(Followup.customer_id, func.max(when))
        .where(Followup.customer_id.in_(customer_ids))
        .group_by(Followup.customer_id)
    )
    return {cid: at for cid, at in db.execute(stmt).all()}


def last_activity(db: Session, opps: list[Opportunity]) -> dict[uuid.UUID, datetime]:
    """最近动态时间 = max(商机动态, 客户动态, 客户跟进, 商机创建时间)。"""
    if not opps:
        return {}
    customer_ids = {o.customer_id for o in opps}
    acts = _latest_activities(db, {o.id for o in opps} | customer_ids)
    fus = _latest_followups(db, customer_ids)
    result: dict[uuid.UUID, datetime] = {}
    for o in opps:
        candidates = [acts.get(o.id), acts.get(o.customer_id), fus.get(o.customer_id), o.created_at]
        result[o.id] = max(c for c in candidates if c is not None)
    return result


def insights(
    db: Session, opps: list[Opportunity], rules: RuleSet | None = None
) -> dict[uuid.UUID, dict[str, Any]]:
    """商机 id → {next_task, last_activity_at, idle_days, stale}。"""
    now = datetime.now(UTC)
    cfg = rules or load_rules()
    tasks = next_tasks(db, [o.id for o in opps], now)
    lasts = last_activity(db, opps)
    out: dict[uuid.UUID, dict[str, Any]] = {}
    for o in opps:
        idle = idle_days_of(lasts[o.id], now)
        out[o.id] = {
            "next_task": tasks.get(o.id),
            "last_activity_at": lasts[o.id],
            "idle_days": idle,
            "stale": is_stale(o.stage, idle, cfg),
        }
    return out
