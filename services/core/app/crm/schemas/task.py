"""任务、通知、同事列表、转移负责人 schema（接口契约 v3 §11、§12、§15、§16）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.common.auth import Role
from app.crm.schemas.common import UserBrief

TaskType = Literal["call", "visit", "email", "meeting", "todo"]
TaskSubject = Literal["customer", "opportunity"]
TaskDue = Literal["today", "overdue", "week"]
TaskStatus = Literal["open", "done"]


class TaskItem(BaseModel):
    id: uuid.UUID
    title: str
    type: TaskType
    due_at: datetime
    done: bool
    done_at: datetime | None
    note: str | None
    subject_type: TaskSubject
    subject_id: uuid.UUID
    subject_name: str | None
    owner: UserBrief | None
    overdue: bool


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime  # 不带时区时按北京时间
    subject_type: TaskSubject
    subject_id: uuid.UUID
    type: TaskType = "todo"
    note: str | None = Field(default=None, max_length=2000)


class TaskUpdate(BaseModel):
    """只修改传入的字段；done=true 完成任务（写 Activity task_done），done=false 重新打开。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_at: datetime | None = None
    note: str | None = Field(default=None, max_length=2000)
    type: TaskType | None = None
    done: bool | None = None


class NextTask(BaseModel):
    id: uuid.UUID
    title: str
    due_at: datetime
    overdue: bool


class UserListItem(BaseModel):
    id: uuid.UUID
    name: str
    role: Role


class NotificationItem(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None
    link: str | None
    read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationItem]
    total: int
    unread: int


class NotificationRead(BaseModel):
    ids: list[uuid.UUID] | None = Field(default=None, max_length=200)


class NotificationReadResult(BaseModel):
    updated: int
    unread: int


class CustomerTransfer(BaseModel):
    customer_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    to_user_id: uuid.UUID


class TransferResult(BaseModel):
    transferred: int
    opportunities: int
    tasks: int
    quotes: int


class HandoverIn(BaseModel):
    """按人一键交接：把 from_user 名下的全部客户和进行中的业务转给 to_user。"""

    from_user_id: uuid.UUID
    to_user_id: uuid.UUID


class HandoverResult(BaseModel):
    """交接（或预览）的数量：客户、未结束商机、未完成任务、未成交报价、回款中的合同。"""

    customers: int
    opportunities: int
    tasks: int
    quotes: int
    contracts: int
