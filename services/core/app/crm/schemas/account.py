"""成员与团队管理（仅管理员）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.common.auth import Role

USERNAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_.-]{2,29}$"


class AccountItem(BaseModel):
    id: uuid.UUID
    username: str | None
    name: str
    role: Role
    team_id: uuid.UUID | None
    team_name: str | None
    active: bool
    must_change_password: bool
    last_login_at: datetime | None
    # 名下客户数：停用的成员还有客户时提示主管交接
    customers: int


class AccountCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    name: str = Field(min_length=1, max_length=50)
    role: Role
    team_id: uuid.UUID | None = None


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    role: Role | None = None
    team_id: uuid.UUID | None = None
    active: bool | None = None


class TempPassword(BaseModel):
    """新建成员 / 重置密码后的临时密码：只在这次响应里出现一次，首次登录必须修改。"""

    account: AccountItem
    temp_password: str


class TeamItem(BaseModel):
    id: uuid.UUID
    name: str
    members: int
    managers: list[str]
    # 团队默认产品线：成员没有从商机进入 AI 时用它对应的行业包；没设时用系统默认行业包
    default_product_line_id: uuid.UUID | None = None
    default_product_line: str | None = None
    pack: str | None = None


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # 不传 = 不改；传 null = 改回系统默认行业包
    default_product_line_id: uuid.UUID | None = None
