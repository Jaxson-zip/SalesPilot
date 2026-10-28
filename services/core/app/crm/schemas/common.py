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
    actor: UserBrief | None
    source: Literal["manual", "agent"]
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
