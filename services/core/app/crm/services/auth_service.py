"""登录：账号密码登录，演示环境另有「演示账户」一键进入；访问口令和失败锁定。

- 账号密码：`users.username` + scrypt 哈希；同一 IP + 账号连续输错 10 次锁 10 分钟。
- 演示账户（`DEMO_LOGIN=true`）：按角色进入固定的演示用户，左下角可以切换；正式使用时关掉。
- 正式模式下演示账号不能用公开的初始密码（DEMO_PASSWORD）登录，先用 `python -m seed.admin` 重置。
- 访问口令（`ACCESS_CODE`）：公网部署时设置，两种登录都要先过口令；
  已登录的用户切换演示账户时带着当前 token，不用再输口令。
"""

import hmac
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role, forget_user, issue_token, verify_token
from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode
from app.common.passwords import hash_password, verify_password, weakness
from app.crm.models import Team, User
from app.crm.schemas.common import UserOut
from app.crm.services.demo import DEMO_LOGINS, DEMO_USERS
from app.rules.loader import solo_mode

RULE_ACCESS_CODE = "access_code"
RULE_LOGIN_LOCKED = "login_locked"
RULE_WEAK_PASSWORD = "weak_password"
RULE_INACTIVE = "account_inactive"
RULE_DEMO_PASSWORD = "demo_password"
MAX_FAILURES = 10
LOCK_SECONDS = 600
_failures: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


class LoginResult(BaseModel):
    token: str
    user: UserOut


class AuthOptions(BaseModel):
    access_code_required: bool
    demo_login: bool


def options() -> AuthOptions:
    s = get_settings()
    return AuthOptions(access_code_required=bool(s.access_code), demo_login=s.demo_login)


def to_user_out(db: Session, user: User) -> UserOut:
    team = db.get(Team, user.team_id) if user.team_id else None
    return UserOut(
        id=user.id,
        name=user.name,
        role=Role(user.role),
        team_id=user.team_id,
        team_name=team.name if team else None,
        username=user.username,
        must_change_password=user.must_change_password,
        solo_mode=solo_mode(),
    )


def me(db: Session, current: CurrentUser) -> UserOut:
    user = db.get(User, current.id)
    if user is None:
        raise BizError(ErrorCode.UNAUTHORIZED)
    return to_user_out(db, user)


def _session(db: Session, user: User) -> LoginResult:
    current = CurrentUser(id=user.id, name=user.name, role=Role(user.role), team_id=user.team_id)
    return LoginResult(
        token=issue_token(current, version=user.token_version), user=to_user_out(db, user)
    )


# ---------- 失败计数 ----------


def _recent(key: str, now: float) -> deque[float]:
    hits = _failures[key]
    while hits and now - hits[0] > LOCK_SECONDS:
        hits.popleft()
    return hits


def _ensure_not_locked(key: str, message: str, rule: str) -> None:
    with _lock:
        if len(_recent(key, time.monotonic())) >= MAX_FAILURES:
            raise BizError(ErrorCode.RATE_LIMITED, message, {"rule": rule})


def _fail(key: str) -> None:
    with _lock:
        now = time.monotonic()
        _recent(key, now).append(now)


def _clear(key: str) -> None:
    with _lock:
        _failures.pop(key, None)


def _has_valid_token(authorization: str | None) -> bool:
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    try:
        verify_token(authorization[7:].strip())
    except BizError:
        return False
    return True


def check_access(code: str | None, authorization: str | None, ip: str | None) -> None:
    """配置了访问口令时：有有效 token（切换账户）或口令正确才放行。"""
    expected = get_settings().access_code
    if not expected or _has_valid_token(authorization):
        return
    key = f"code:{ip or '-'}"
    _ensure_not_locked(key, "口令错误次数过多，请 10 分钟后再试", RULE_ACCESS_CODE)
    if code and hmac.compare_digest(code.encode(), expected.encode()):
        _clear(key)
        return
    _fail(key)
    message = "请输入访问口令" if not code else "访问口令不正确"
    raise BizError(ErrorCode.UNAUTHORIZED, message, {"rule": RULE_ACCESS_CODE})


# ---------- 登录 ----------


def password_login(db: Session, username: str, password: str, ip: str | None) -> LoginResult:
    name = username.strip().lower()
    key = f"pw:{ip or '-'}:{name}"
    _ensure_not_locked(key, "密码错误次数过多，请 10 分钟后再试", RULE_LOGIN_LOCKED)
    user = db.scalars(select(User).where(func.lower(User.username) == name)).first()
    if user is None or not verify_password(password, user.password_hash):
        _fail(key)
        raise BizError(ErrorCode.UNAUTHORIZED, "账号或密码不正确")
    if not user.active:
        raise BizError(ErrorCode.FORBIDDEN, "账号已停用，请联系管理员", {"rule": RULE_INACTIVE})
    if _default_demo_password(user, password):
        raise BizError(
            ErrorCode.FORBIDDEN,
            "演示账号还在用公开的初始密码，正式模式下不能登录；请在服务器上运行 "
            f"python -m seed.admin {user.username} 重置密码",
            {"rule": RULE_DEMO_PASSWORD},
        )
    _clear(key)
    user.last_login_at = datetime.now(UTC)
    db.flush()
    return _session(db, user)


def _default_demo_password(user: User, password: str) -> bool:
    """正式模式（DEMO_LOGIN=false）下，演示账号不能用 README 里公开的初始密码登录。"""
    settings = get_settings()
    if settings.demo_login or user.id not in DEMO_LOGINS:
        return False
    return hmac.compare_digest(password.encode(), settings.demo_password.encode())


def demo_login(db: Session, role: Role) -> LoginResult:
    """演示账户：按角色进入固定的演示用户（DEMO_LOGIN=false 时关闭）。"""
    if not get_settings().demo_login:
        raise BizError(
            ErrorCode.FORBIDDEN, "演示账户已关闭，请用账号密码登录", {"rule": "demo_off"}
        )
    demo = DEMO_USERS[role]
    user = db.get(User, demo.id)
    if user is None:  # 还没导入种子数据：按固定身份签发，和以前的假登录一致
        out = UserOut(id=demo.id, name=demo.name, role=demo.role, team_id=demo.team_id)
        return LoginResult(token=issue_token(demo), user=out)
    if not user.active:
        raise BizError(ErrorCode.FORBIDDEN, "该演示账户已停用", {"rule": RULE_INACTIVE})
    user.last_login_at = datetime.now(UTC)
    db.flush()
    return _session(db, user)


def change_password(db: Session, current: CurrentUser, old: str, new: str) -> LoginResult:
    """改自己的密码：旧密码要对、新密码要够强；成功后旧 token 全部作废，返回新 token。"""
    user = db.get(User, current.id, with_for_update=True)
    if user is None:
        raise BizError(ErrorCode.UNAUTHORIZED)
    if not verify_password(old, user.password_hash):
        raise BizError(ErrorCode.VALIDATION, "原密码不正确", {"rule": "wrong_password"})
    reason = weakness(new)
    if reason:
        raise BizError(ErrorCode.VALIDATION, reason, {"rule": RULE_WEAK_PASSWORD})
    if old == new:
        raise BizError(ErrorCode.VALIDATION, "新密码不能和原密码相同", {"rule": "same_password"})
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.token_version += 1
    db.flush()
    forget_user(user.id)
    return _session(db, user)
