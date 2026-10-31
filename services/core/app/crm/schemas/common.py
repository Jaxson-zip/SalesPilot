"""通用 schema：分页、用户 / 客户 / 商机简要信息、动态、附件（接口契约 §0）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.common.auth import Role


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role: Role
    team_id: uuid.UUID | None = None
    team_name: str | None = None
    username: str | None = None
    # 管理员新建 / 重置密码后为 true：登录后先改密码
    must_change_password: bool = False
    # 个人模式（业务规则 org.solo_mode）：前端隐藏团队相关页面，主管显示系统配置
    solo_mode: bool = False


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page[T](BaseModel):
    items: list[T]
    total: int


class CustomerBrief(BaseModel):
    id: uuid.UUID
    name: str


class OppBrief(BaseModel):
    id: uuid.UUID
    name: str


class ProductLineBrief(BaseModel):
    id: uuid.UUID
    name: str
    pack: str


class CodeRef(BaseModel):
    id: uuid.UUID
    code: str


class ActivityOut(BaseModel):
    id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    # 动态流里显示「哪一单」：客户 / 商机名称，报价 / 合同 / 报销编号；查不到为 None
    subject_name: str | None = None
    actor: UserBrief | None
    source: Literal["manual", "agent", "system"]
    action: str
    content: str | None
    created_at: datetime


AttachmentKind = Literal["invoice", "receipt", "other"]


class AttachmentOut(BaseModel):
    id: uuid.UUID
    kind: AttachmentKind
    file_name: str
    mime: str
    size: int
    url: str
