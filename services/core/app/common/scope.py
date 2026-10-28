"""数据范围过滤（开发规范 §1.3）：sales → owner_id；manager → team_id；admin → 不过滤。

单条记录的可见性（can_see）另外放开本团队的公海记录（负责人为空，B5），列表仍按上面过滤。

所有 service 的列表 / 详情查询都必须经过 apply_scope，接口和 Agent 工具共用。
"""

from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import Select, false, or_

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode


class View(StrEnum):
    MINE = "mine"
    TEAM = "team"
    ALL = "all"


class ScopedModel(Protocol):
    owner_id: Any
    team_id: Any


def max_view_of(role: Role) -> View:
    return {Role.SALES: View.MINE, Role.MANAGER: View.TEAM, Role.ADMIN: View.ALL}[role]


def resolve_view(user: CurrentUser, requested: View | None) -> View:
    """请求的视图不能超过角色允许的最大范围；超过时按最大范围处理（不报错，前端视图切换更友好）。"""
    order = [View.MINE, View.TEAM, View.ALL]
    allowed = max_view_of(user.role)
    if requested is None:
        return allowed
    return requested if order.index(requested) <= order.index(allowed) else allowed


def apply_scope[S: Select[Any]](
    stmt: S, model: type[ScopedModel], user: CurrentUser, view: View | None = None
) -> S:
    """给查询加上数据范围条件。model 需要有 owner_id 和 team_id 列。"""
    effective = resolve_view(user, view)
    if effective is View.MINE:
        return stmt.where(model.owner_id == user.id)
    if effective is View.TEAM:
        if user.team_id is None:
            return stmt.where(false())
        return stmt.where(or_(model.team_id == user.team_id, model.owner_id == user.id))
    return stmt


def ensure_visible(obj: ScopedModel | None, user: CurrentUser) -> None:
    """单条记录权限校验：不存在或不可见都返回 40401，避免泄露存在性。"""
    if obj is None or not can_see(obj, user):
        raise BizError(ErrorCode.NOT_FOUND)


def can_see(obj: ScopedModel, user: CurrentUser) -> bool:
    if user.role is Role.ADMIN:
        return True
    if obj.owner_id == user.id:
        return True
    if obj.owner_id is None and user.team_id is not None and obj.team_id == user.team_id:
        return True  # 本团队公海（B5）：只读可见，领取后才能修改
    return user.role is Role.MANAGER and user.team_id is not None and obj.team_id == user.team_id
