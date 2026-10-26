"""同事列表与站内通知接口（接口契约 v3 §11、§15）。"""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import Page
from app.crm.schemas.task import (
    NotificationList,
    NotificationRead,
    NotificationReadResult,
    UserListItem,
)
from app.crm.services import notification_service, user_service

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/users", response_model=ApiResponse[Page[UserListItem]])
def list_users(
    user: CurrentUserDep, db: DbDep, scope: Literal["team", "all"] = "team"
) -> ApiResponse[Page[UserListItem]]:
    """销售 / 主管始终返回本团队；管理员不属于任何团队，始终返回全部（scope 仅为兼容保留）。"""
    del scope
    return ok(user_service.list_users(db, user))


@router.get("/notifications", response_model=ApiResponse[NotificationList])
def list_notifications(
    user: CurrentUserDep,
    db: DbDep,
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[NotificationList]:
    return ok(notification_service.list_notifications(db, user, unread, limit))


@router.post("/notifications/read", response_model=ApiResponse[NotificationReadResult])
def mark_read(
    user: CurrentUserDep, db: DbDep, body: NotificationRead | None = None
) -> ApiResponse[NotificationReadResult]:
    return ok(notification_service.mark_read(db, user, body.ids if body else None))
