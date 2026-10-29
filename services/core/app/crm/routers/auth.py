"""登录（账号密码 / 演示账户，可选访问口令）、改密码与当前用户。"""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.common.auth import CurrentUserDep, Role, decode_token
from app.common.response import ApiResponse, ok
from app.crm.routers.audit import client_ip
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import UserOut
from app.crm.services import audit_service, auth_service
from app.crm.services.auth_service import AuthOptions, LoginResult

router = APIRouter(prefix="/api", tags=["auth"])


class MockLoginIn(BaseModel):
    """演示账户登录（DEMO_LOGIN 开启时可用）。"""

    role: Role
    # 服务端配置了 ACCESS_CODE 时必填（已登录切换账户时可以不带）
    access_code: str | None = Field(default=None, max_length=100)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)
    access_code: str | None = Field(default=None, max_length=100)


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=1, max_length=100)


def _logged_in(result: LoginResult) -> LoginResult:
    action, label = audit_service.LOGIN
    audit_service.record(
        decode_token(result.token), audit_service.AuditEntry(action=action, label=label)
    )
    return result


@router.get("/auth/options", response_model=ApiResponse[AuthOptions])
def auth_options() -> ApiResponse[AuthOptions]:
    return ok(auth_service.options())


@router.post("/auth/login", response_model=ApiResponse[LoginResult])
def login(body: LoginIn, request: Request, db: DbDep) -> ApiResponse[LoginResult]:
    ip = client_ip(request)
    auth_service.check_access(body.access_code, None, ip)
    return ok(_logged_in(auth_service.password_login(db, body.username, body.password, ip)))


@router.post("/auth/mock-login", response_model=ApiResponse[LoginResult])
def mock_login(
    body: MockLoginIn,
    request: Request,
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiResponse[LoginResult]:
    auth_service.check_access(body.access_code, authorization, client_ip(request))
    return ok(_logged_in(auth_service.demo_login(db, body.role)))


@router.post("/auth/password", response_model=ApiResponse[LoginResult])
def change_password(
    body: PasswordChange, user: CurrentUserDep, db: DbDep
) -> ApiResponse[LoginResult]:
    return ok(auth_service.change_password(db, user, body.old_password, body.new_password))


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: CurrentUserDep, db: DbDep) -> ApiResponse[UserOut]:
    return ok(auth_service.me(db, user))
