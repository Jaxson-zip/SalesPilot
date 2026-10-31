"""JWT 签发 / 校验与 CurrentUser 依赖。

token 里带 user_id / name / role / team_id / ver。每个请求按 user_id 查库（短时缓存）：
账号停用、改密码（ver 变了）立即失效；角色、团队、姓名以库里为准，管理员改了马上生效。
数据库暂时连不上时退回 token 里的信息，不让整个系统跟着不可用。
"""

import logging
import threading
import time
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


logger = logging.getLogger(__name__)
CACHE_SECONDS = 15
_cache: dict[uuid.UUID, tuple[float, "_Account"]] = {}
_cache_lock = threading.Lock()


class _Account(BaseModel):
    name: str
    role: Role
    team_id: uuid.UUID | None
    active: bool
    token_version: int


def forget_user(user_id: uuid.UUID | None = None) -> None:
    """管理员改了成员（或改密码）后清缓存，下一个请求就按新状态校验。"""
    with _cache_lock:
        if user_id is None:
            _cache.clear()
        else:
            _cache.pop(user_id, None)


def _load_account(user_id: uuid.UUID) -> "_Account | None":
    from sqlalchemy import text

    from app.common.db import session_scope

    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(user_id)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    with session_scope() as db:
        row = db.execute(
            text("select name, role, team_id, active, token_version from users where id = :id"),
            {"id": user_id},
        ).first()
    if row is None:  # 不缓存「不存在」：刚建好的账号马上能用
        return None
    account = _Account(**row._mapping)
    with _cache_lock:
        _cache[user_id] = (now, account)
    return account


def issue_token(user: CurrentUser, expire_minutes: int | None = None, version: int = 0) -> str:
    settings = get_settings()
    minutes = expire_minutes if expire_minutes is not None else settings.jwt_expire_minutes
    payload = {
        "sub": str(user.id),
        "name": user.name,
        "role": user.role.value,
        "team_id": str(user.team_id) if user.team_id else None,
        "ver": version,
        "exp": datetime.now(UTC) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def _claims(token: str) -> tuple[CurrentUser, int]:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
        team_id = payload.get("team_id")
        user = CurrentUser(
            id=uuid.UUID(payload["sub"]),
            name=payload["name"],
            role=Role(payload["role"]),
            team_id=uuid.UUID(team_id) if team_id else None,
        )
        return user, int(payload.get("ver", 0))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise BizError(ErrorCode.UNAUTHORIZED) from exc


def decode_token(token: str) -> CurrentUser:
    """只校验签名和有效期（不查库）：审计日志等内部场景用。"""
    return _claims(token)[0]


def verify_token(token: str) -> CurrentUser:
    """校验 token 并按库里的账号状态返回当前用户：停用 / 已改密码 / 不存在都算失效。"""
    claimed, version = _claims(token)
    try:
        account = _load_account(claimed.id)
    except Exception:  # 数据库不可用：退回 token 里的信息
        logger.warning("user lookup failed, falling back to token claims", exc_info=True)
        return claimed
    if account is None or not account.active or account.token_version != version:
        raise BizError(ErrorCode.UNAUTHORIZED, "账号已停用或登录已失效，请重新登录")
    return CurrentUser(id=claimed.id, name=account.name, role=account.role, team_id=account.team_id)


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise BizError(ErrorCode.UNAUTHORIZED)
    return verify_token(authorization.split(" ", 1)[1].strip())


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_optional_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser | None:
    """公开接口用：带了有效 token 返回登录用户，没带或无效返回 None（不报 401）。"""
    try:
        return get_current_user(authorization)
    except BizError:
        return None


OptionalUserDep = Annotated[CurrentUser | None, Depends(get_optional_user)]


def require_roles(*roles: Role) -> object:
    """路由依赖：限制角色，例如审批接口只允许 manager。"""

    def _checker(user: CurrentUserDep) -> CurrentUser:
        if user.role not in roles:
            raise BizError(ErrorCode.FORBIDDEN)
        return user

    return Depends(_checker)
