"""动态记录：挂在客户 / 商机 / 报价 / 合同 / 报销上。

owner_id / team_id 跟随被操作对象（subject）的负责人，因此动态的可见范围与业务数据一致：
主管改了销售的商机阶段，销售本人也能在动态里看到。
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.scope import ScopedModel, View, apply_scope
from app.crm.models import Activity, User
from app.crm.schemas.common import ActivityOut, UserBrief

MAX_LIMIT = 100


def record(
    db: Session,
    user: CurrentUser,
    subject_type: str,
    subject_id: uuid.UUID,
    action: str,
    content: str | None = None,
    source: str = "manual",
    subject: ScopedModel | None = None,
) -> Activity:
    if subject is not None and subject.owner_id is not None:
        owner_id, team_id = subject.owner_id, subject.team_id
    else:
        owner_id, team_id = user.id, user.team_id
    activity = Activity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=None if source == "agent" else user.id,
        source=source,
        action=action,
        content=content,
        owner_id=owner_id,
        team_id=team_id,
    )
    db.add(activity)
    db.flush()
    return activity


def record_system(
    db: Session,
    subject_type: str,
    subject_id: uuid.UUID,
    action: str,
    content: str | None,
    team_id: uuid.UUID | None,
    owner_id: uuid.UUID | None = None,
) -> Activity:
    """定时任务等系统操作留下的动态：没有操作人，来源记为 system。"""
    activity = Activity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=None,
        source="system",
        action=action,
        content=content,
        owner_id=owner_id,
        team_id=team_id,
    )
    db.add(activity)
    db.flush()
    return activity


def _to_out(row: Any) -> ActivityOut:
    a: Activity = row.Activity
    actor = UserBrief(id=a.actor_id, name=row.actor_name) if a.actor_id and row.actor_name else None
    return ActivityOut(
        id=a.id,
        subject_type=a.subject_type,
        subject_id=a.subject_id,
        actor=actor,
        source="agent" if a.source == "agent" else "manual",
        action=a.action,
        content=a.content,
        created_at=a.created_at,
    )


def list_activities(
    db: Session,
    user: CurrentUser,
    view: View | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[ActivityOut]:
    """动态流：按数据范围过滤，最新的在前。"""
    stmt = select(Activity, User.name.label("actor_name")).outerjoin(
        User, User.id == Activity.actor_id
    )
    if subject_type:
        stmt = stmt.where(Activity.subject_type == subject_type)
    if subject_id:
        stmt = stmt.where(Activity.subject_id == subject_id)
    stmt = apply_scope(stmt, Activity, user, view)
    stmt = stmt.order_by(Activity.created_at.desc(), Activity.id).limit(min(limit, MAX_LIMIT))
    return [_to_out(r) for r in db.execute(stmt).all()]


def list_for_subject(db: Session, subject_id: uuid.UUID, limit: int = 50) -> list[ActivityOut]:
    """详情页用：调用方已校验过 subject 的可见性，这里不再按范围过滤。"""
    stmt = (
        select(Activity, User.name.label("actor_name"))
        .outerjoin(User, User.id == Activity.actor_id)
        .where(Activity.subject_id == subject_id)
        .order_by(Activity.created_at.desc(), Activity.id)
        .limit(limit)
    )
    return [_to_out(r) for r in db.execute(stmt).all()]
