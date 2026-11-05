"""JWT 签发 / 校验与 CurrentUser 依赖。

token 里带 user_id / name / role / team_id / ver。每个请求按 user_id 查库（短时缓存）：
账号停用、改密码（ver 变了）立即失效；角色、团队、姓名以库里为准，管理员改了马上生效。
数据库暂时连不上时退回 token 里的信息，不让整个系统跟着不可用。
"""

import logging
import threading
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

import jwt
from fastapi import Depends, Header, Request
from pydantic import BaseModel

from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode

JWT_ALGORITHM = "HS256"
# 网页登录用 HttpOnly Cookie 保存 token（JS 读不到）；脚本 / 测试仍可用 Authorization: Bearer
SESSION_COOKIE = "sp_session"
# CSRF：Cookie 鉴权的写请求必须带这个自定义请求头。
# 跨站页面带不了自定义头（需要 CORS 预检，core 不放行）
CSRF_HEADER = "X-Requested-With"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RULE_CSRF = "csrf"


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
    except Exception as exc:
        # 正式模式：核验不了就不放行（token 里的角色、团队可能已经过时，账号也可能已停用）。
        # 演示模式沿用 token 里的信息，数据库短暂不可用时页面还能看。
        logger.warning("user lookup failed", exc_info=True)
        if not get_settings().demo_login:
            raise BizError(ErrorCode.UNAVAILABLE, "暂时无法核验账号状态，请稍后再试") from exc
        return claimed
    if account is None or not account.active or account.token_version != version:
        raise BizError(ErrorCode.UNAUTHORIZED, "账号已停用或登录已失效，请重新登录")
    return CurrentUser(id=claimed.id, name=account.name, role=account.role, team_id=account.team_id)


def bearer_token(authorization: str | None) -> str | None:
    """从 Authorization 头取 Bearer token；没有或格式不对返回 None。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip() or None


def request_token(authorization: str | None, cookies: Mapping[str, str]) -> tuple[str | None, bool]:
    """取请求里的 token：Bearer 头优先，其次 HttpOnly Cookie。返回 (token, 是否来自 Cookie)。"""
    token = bearer_token(authorization)
    if token:
        return token, False
    cookie = cookies.get(SESSION_COOKIE) or None
    return cookie, cookie is not None


def check_csrf(method: str, headers: Mapping[str, str]) -> None:
    """Cookie 鉴权的写请求必须带 X-Requested-With。

    浏览器会自动带 Cookie，跨站伪造的请求却带不了自定义头。
    """
    if method.upper() not in SAFE_METHODS and not headers.get(CSRF_HEADER):
        raise BizError(
            ErrorCode.FORBIDDEN,
            "请求缺少 X-Requested-With 请求头（CSRF 防护）",
            {"rule": RULE_CSRF},
        )


def get_current_user(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> CurrentUser:
    token, from_cookie = request_token(authorization, request.cookies)
    if not token:
        raise BizError(ErrorCode.UNAUTHORIZED)
    if from_cookie:
        check_csrf(request.method, request.headers)
    return verify_token(token)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_optional_user(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> CurrentUser | None:
    """公开接口用：带了有效 token 返回登录用户，没带或无效返回 None（不报 401）。"""
    try:
        return get_current_user(request, authorization)
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
