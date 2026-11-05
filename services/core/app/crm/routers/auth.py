"""登录（账号密码 / 演示账户，可选访问口令）、改密码、退出登录与当前用户。

登录成功写 HttpOnly Cookie（见 app/common/session_cookie.py）；浏览器发起的登录响应体里不带 token。
"""

from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, Field

from app.common.auth import CurrentUserDep, Role, decode_token, request_token
from app.common.response import ApiResponse, ok
from app.common.session_cookie import clear_session_cookie, from_browser, set_session_cookie
from app.crm.routers.audit import client_ip
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import UserOut
from app.crm.services import audit_service, auth_service
from app.crm.services.auth_service import AuthOptions, LoginResult

router = APIRouter(prefix="/api", tags=["auth"])


class MockLoginIn(BaseModel):
    """演示账户登录（DEMO_LOGIN 开启时可用）。"""

    role: Role
    # 同一角色有多个演示账户（如华东组的陈静 / 刘洋）时指定登录名；不填进入该角色的默认演示账户
    username: str | None = Field(default=None, max_length=50)
    # 服务端配置了 ACCESS_CODE 时必填（已登录切换账户时可以不带）
    access_code: str | None = Field(default=None, max_length=100)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)
    access_code: str | None = Field(default=None, max_length=100)


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=1, max_length=100)


def _issued(result: LoginResult, request: Request, response: Response) -> LoginResult:
    """写登录 Cookie；浏览器里的请求把响应体里的 token 去掉（JS 拿不到 token）。"""
    if result.token:
        set_session_cookie(response, request, result.token)
    return result.model_copy(update={"token": None}) if from_browser(request) else result


def _logged_in(result: LoginResult, request: Request, response: Response) -> LoginResult:
    action, label = audit_service.LOGIN
    if result.token:
        audit_service.record(
            decode_token(result.token), audit_service.AuditEntry(action=action, label=label)
        )
    return _issued(result, request, response)


@router.get("/auth/options", response_model=ApiResponse[AuthOptions])
def auth_options() -> ApiResponse[AuthOptions]:
    return ok(auth_service.options())


@router.post("/auth/login", response_model=ApiResponse[LoginResult])
def login(
    body: LoginIn, request: Request, response: Response, db: DbDep
) -> ApiResponse[LoginResult]:
    ip = client_ip(request)
    auth_service.check_access(body.access_code, None, ip)
    result = auth_service.password_login(db, body.username, body.password, ip)
    return ok(_logged_in(result, request, response))


@router.post("/auth/mock-login", response_model=ApiResponse[LoginResult])
def mock_login(
    body: MockLoginIn,
    request: Request,
    response: Response,
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiResponse[LoginResult]:
    # 已登录（Bearer 或 Cookie）切换账户时不用再输访问口令
    current, _ = request_token(authorization, request.cookies)
    auth_service.check_access(body.access_code, current, client_ip(request))
    result = auth_service.demo_login(db, body.role, body.username)
    return ok(_logged_in(result, request, response))


@router.post("/auth/password", response_model=ApiResponse[LoginResult])
def change_password(
    body: PasswordChange, request: Request, response: Response, user: CurrentUserDep, db: DbDep
) -> ApiResponse[LoginResult]:
    result = auth_service.change_password(db, user, body.old_password, body.new_password)
    return ok(_issued(result, request, response))


@router.post("/auth/logout", response_model=ApiResponse[None])
def logout(request: Request, response: Response) -> ApiResponse[None]:
    """退出登录：清掉登录 Cookie（不要求已登录；token 本身到期前仍有效，改密码才会全部作废）。"""
    clear_session_cookie(response, request)
    return ok(None)


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: CurrentUserDep, db: DbDep) -> ApiResponse[UserOut]:
    return ok(auth_service.me(db, user))
