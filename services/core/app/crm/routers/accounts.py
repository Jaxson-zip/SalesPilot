"""成员与团队管理（仅管理员）。"""

import uuid

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.schemas.account import (
    AccountCreate,
    AccountItem,
    AccountUpdate,
    TeamIn,
    TeamItem,
    TempPassword,
)
from app.crm.services import account_service

router = APIRouter(prefix="/api/admin", tags=["accounts"])


@router.get("/users", response_model=ApiResponse[list[AccountItem]])
def list_accounts(user: CurrentUserDep, db: DbDep) -> ApiResponse[list[AccountItem]]:
    return ok(account_service.list_accounts(db, user))


@router.post("/users", response_model=ApiResponse[TempPassword])
def create_account(
    body: AccountCreate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TempPassword]:
    return ok(account_service.create_account(db, user, body))


@router.patch("/users/{user_id}", response_model=ApiResponse[AccountItem])
def update_account(
    user_id: uuid.UUID, body: AccountUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[AccountItem]:
    return ok(account_service.update_account(db, user, user_id, body))


@router.post("/users/{user_id}/reset-password", response_model=ApiResponse[TempPassword])
def reset_password(
    user_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TempPassword]:
    return ok(account_service.reset_password(db, user, user_id))


@router.get("/teams", response_model=ApiResponse[list[TeamItem]])
def list_teams(user: CurrentUserDep, db: DbDep) -> ApiResponse[list[TeamItem]]:
    return ok(account_service.list_teams(db, user))


@router.post("/teams", response_model=ApiResponse[TeamItem])
def create_team(body: TeamIn, user: CurrentUserDep, db: DbDep) -> ApiResponse[TeamItem]:
    return ok(account_service.create_team(db, user, body))


@router.patch("/teams/{team_id}", response_model=ApiResponse[TeamItem])
def rename_team(
    team_id: uuid.UUID, body: TeamIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TeamItem]:
    return ok(account_service.rename_team(db, user, team_id, body))
