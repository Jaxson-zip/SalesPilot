"""假登录：按角色签发 JWT（演示用，不做真实登录注册）。"""

from pydantic import BaseModel

from app.common.auth import CurrentUser, Role, issue_token
from app.crm.schemas.common import UserOut
from app.crm.services.demo import DEMO_USERS


class LoginResult(BaseModel):
    token: str
    user: UserOut


def to_user_out(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, name=user.name, role=user.role.value, team_id=user.team_id)


def mock_login(role: Role) -> LoginResult:
    """演示身份使用固定 UUID，与 seed 写入数据库的用户一致，因此不需要查库。"""
    user = DEMO_USERS[role]
    return LoginResult(token=issue_token(user), user=to_user_out(user))
