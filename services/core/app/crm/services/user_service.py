"""同事列表 service（接口契约 v3 §11）：报销参与人、转移负责人、任务指派用。

销售 / 主管：只返回本团队成员（scope=all 也按本团队处理）；管理员不属于团队，返回全部用户。
"""

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.crm.models import User
from app.crm.schemas.common import Page
from app.crm.schemas.task import UserListItem

ROLE_ORDER = {Role.MANAGER.value: 0, Role.SALES.value: 1, Role.ADMIN.value: 2}


def list_users(
    db: Session, user: CurrentUser, include_inactive: bool = False
) -> Page[UserListItem]:
    stmt = select(User)
    if user.role is not Role.ADMIN:
        stmt = stmt.where(User.team_id == user.team_id) if user.team_id else stmt.where(false())
    if not include_inactive:
        stmt = stmt.where(User.active.is_(True))
    rows = sorted(db.scalars(stmt).all(), key=lambda u: (ROLE_ORDER.get(u.role, 9), u.name))
    items = [UserListItem(id=u.id, name=u.name, role=u.role, active=u.active) for u in rows]
    return Page[UserListItem](items=items, total=len(items))
