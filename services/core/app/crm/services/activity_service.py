"""动态记录：挂在客户 / 商机等对象上，team_id 冗余存储用于团队范围过滤。"""

import uuid

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.models import Activity


def record(
    db: Session,
    user: CurrentUser,
    subject_type: str,
    subject_id: uuid.UUID,
    action: str,
    content: str | None = None,
    source: str = "manual",
) -> Activity:
    activity = Activity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=None if source == "agent" else user.id,
        source=source,
        action=action,
        content=content,
        owner_id=user.id,
        team_id=user.team_id,
    )
    db.add(activity)
    db.flush()
    return activity


# TODO: list_activities(db, user, member_id=None) —— 工作台「我的动态 / 团队动态」
