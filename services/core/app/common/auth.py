"""JWT 签发 / 校验与 CurrentUser 依赖。

演示用假登录：token 里携带 user_id / name / role / team_id。
"""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

import jwt
from fastapi import Depends, Header
from pydantic import BaseModel

from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode

JWT_ALGORITHM = "HS256"


class Role(StrEnum):
    SALES = "sales"
    MANAGER = "manager"
    ADMIN = "admin"


class CurrentUser(BaseModel):
    id: uuid.UUID
    name: str
    role: Role
    team_id: uuid.UUID | None = None


def issue_token(user: CurrentUser, expire_minutes: int | None = None) -> str:
    settings = get_settings()
    minutes = expire_minutes if expire_minutes is not None else settings.jwt_expire_minutes
    payload = {
        "sub": str(user.id),
        "name": user.name,
        "role": user.role.value,
        "team_id": str(user.team_id) if user.team_id else None,
        "exp": datetime.now(UTC) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
        team_id = payload.get("team_id")
        return CurrentUser(
            id=uuid.UUID(payload["sub"]),
            name=payload["name"],
            role=Role(payload["role"]),
            team_id=uuid.UUID(team_id) if team_id else None,
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise BizError(ErrorCode.UNAUTHORIZED) from exc


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise BizError(ErrorCode.UNAUTHORIZED)
    return decode_token(authorization.split(" ", 1)[1].strip())


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(*roles: Role) -> object:
    """路由依赖：限制角色，例如审批接口只允许 manager。"""

    def _checker(user: CurrentUserDep) -> CurrentUser:
        if user.role not in roles:
            raise BizError(ErrorCode.FORBIDDEN)
        return user

    return Depends(_checker)
