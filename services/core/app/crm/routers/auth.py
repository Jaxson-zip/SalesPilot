"""假登录与当前用户。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.common.auth import CurrentUserDep, Role, decode_token
from app.common.response import ApiResponse, ok
from app.crm.schemas.common import UserOut
from app.crm.services import audit_service, auth_service
from app.crm.services.auth_service import LoginResult

router = APIRouter(prefix="/api", tags=["auth"])


class MockLoginIn(BaseModel):
    role: Role


@router.post("/auth/mock-login", response_model=ApiResponse[LoginResult])
def mock_login(body: MockLoginIn) -> ApiResponse[LoginResult]:
    result = auth_service.mock_login(body.role)
    action, label = audit_service.LOGIN
    audit_service.record(
        decode_token(result.token), audit_service.AuditEntry(action=action, label=label)
    )
    return ok(result)


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: CurrentUserDep) -> ApiResponse[UserOut]:
    return ok(auth_service.to_user_out(user))
