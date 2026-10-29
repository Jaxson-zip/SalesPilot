"""演示登录：选演示账户按角色签发 JWT（不做真实注册）。

部署到公网时在 .env 设置 ACCESS_CODE：没有有效 token 的登录请求必须带正确口令；
已登录的用户切换演示账户时带着当前 token，不用再输口令。同一 IP 口令错误过多会暂时锁定。
"""

import hmac
import threading
import time
from collections import defaultdict, deque

from pydantic import BaseModel

from app.common.auth import CurrentUser, Role, decode_token, issue_token
from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode
from app.crm.schemas.common import UserOut
from app.crm.services.demo import DEMO_USERS


class LoginResult(BaseModel):
    token: str
    user: UserOut


def to_user_out(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, name=user.name, role=user.role.value, team_id=user.team_id)


RULE_ACCESS_CODE = "access_code"
MAX_FAILURES = 10
LOCK_SECONDS = 600
_failures: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


class AuthOptions(BaseModel):
    access_code_required: bool


def options() -> AuthOptions:
    return AuthOptions(access_code_required=bool(get_settings().access_code))


def _has_valid_token(authorization: str | None) -> bool:
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    try:
        decode_token(authorization[7:].strip())
    except BizError:
        return False
    return True


def _recent_failures(ip: str, now: float) -> deque[float]:
    hits = _failures[ip]
    while hits and now - hits[0] > LOCK_SECONDS:
        hits.popleft()
    return hits


def check_access(code: str | None, authorization: str | None, ip: str | None) -> None:
    """配置了访问口令时：有有效 token（切换账户）或口令正确才放行。"""
    expected = get_settings().access_code
    if not expected or _has_valid_token(authorization):
        return
    key, now = ip or "-", time.monotonic()
    with _lock:
        hits = _recent_failures(key, now)
        if len(hits) >= MAX_FAILURES:
            raise BizError(
                ErrorCode.RATE_LIMITED, "口令错误次数过多，请 10 分钟后再试",
                {"rule": RULE_ACCESS_CODE},
            )  # fmt: skip
        if code and hmac.compare_digest(code.encode(), expected.encode()):
            hits.clear()
            return
        hits.append(now)
    message = "请输入访问口令" if not code else "访问口令不正确"
    raise BizError(ErrorCode.UNAUTHORIZED, message, {"rule": RULE_ACCESS_CODE})


def mock_login(role: Role) -> LoginResult:
    """演示身份使用固定 UUID，与 seed 写入数据库的用户一致，因此不需要查库。"""
    user = DEMO_USERS[role]
    return LoginResult(token=issue_token(user), user=to_user_out(user))
