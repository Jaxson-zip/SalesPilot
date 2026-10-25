"""客户 schema（字段名与前端约定一致，金额单位：分）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.crm.schemas.common import UserBrief

Level = Literal["A", "B", "C"]


class CustomerListItem(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None
    level: str
    owner: UserBrief | None
    website: str | None
    opportunity_amount: int
    last_followup_at: datetime | None


class CustomerDetail(CustomerListItem):
    size: str | None
    address: str | None
    annual_budget: int | None
    tags: list[str]
    created_at: datetime


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=50)
    level: Level = "C"
    size: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=200)
    annual_budget: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=20)


class CustomerBrief(BaseModel):
    """Agent search_customer 的返回项。"""

    id: uuid.UUID
    name: str
    industry: str | None
    owner: UserBrief | None
