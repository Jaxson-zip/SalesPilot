"""客户 schema（字段名与前端约定一致，金额单位：分）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.crm.schemas.common import UserBrief
from app.crm.schemas.fields import Amount, CustomerName, Website

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
    name: CustomerName
    industry: str | None = Field(default=None, max_length=50)
    level: Level = "C"
    size: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=200)
    website: Website = None
    annual_budget: Amount | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)


class CustomerUpdate(BaseModel):
    """行内编辑（U10）：只修改传入的字段；name / level 传 null 视为不修改。"""

    name: CustomerName | None = None
    industry: str | None = Field(default=None, max_length=50)
    level: Level | None = None
    size: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=200)
    website: Website = None
    annual_budget: Amount | None = None


class PoolRelease(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class SimilarCustomer(BaseModel):
    """新建客户时的查重提示。看不到的客户只给名称和负责人，不给 id。"""

    id: uuid.UUID | None
    name: str
    owner_name: str | None
    exact: bool  # 去掉「有限公司」等后缀后名称相同
    visible: bool


class CustomerSearchItem(BaseModel):
    """Agent search_customer 的返回项。"""

    id: uuid.UUID
    name: str
    industry: str | None
    level: str  # 客户等级 A / B / C
    owner: UserBrief | None
