"""演示登录（可选访问口令）与当前用户。"""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.common.auth import CurrentUserDep, Role, decode_token
from app.common.response import ApiResponse, ok
from app.crm.routers.audit import client_ip
from app.crm.schemas.common import UserOut
from app.crm.services import audit_service, auth_service
from app.crm.services.auth_service import AuthOptions, LoginResult

router = APIRouter(prefix="/api", tags=["auth"])


class MockLoginIn(BaseModel):
    role: Role
    # 服务端配置了 ACCESS_CODE 时必填（已登录切换账户时可以不带）
    access_code: str | None = Field(default=None, max_length=100)


@router.get("/auth/options", response_model=ApiResponse[AuthOptions])
def auth_options() -> ApiResponse[AuthOptions]:
    return ok(auth_service.options())


@router.post("/auth/mock-login", response_model=ApiResponse[LoginResult])
def mock_login(
    body: MockLoginIn,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiResponse[LoginResult]:
    auth_service.check_access(body.access_code, authorization, client_ip(request))
    result = auth_service.mock_login(body.role)
    action, label = audit_service.LOGIN
    audit_service.record(
        decode_token(result.token), audit_service.AuditEntry(action=action, label=label)
    )
    return ok(result)


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: CurrentUserDep) -> ApiResponse[UserOut]:
    return ok(auth_service.to_user_out(user))
