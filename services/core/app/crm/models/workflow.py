"""任务（下一步行动）与站内通知（接口契约 v3 §12、§15）。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import OwnedMixin, TimestampMixin


class Task(OwnedMixin, Base):
    """任务挂在客户或商机上；owner / team 跟随所挂对象的负责人（转移客户时一起转）。"""

    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="todo")  # call/visit/email/meeting/todo
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    subject_type: Mapped[str] = mapped_column(String(20))  # customer / opportunity
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)


class Notification(TimestampMixin, Base):
    """站内通知：只属于接收人本人。dedupe_key 用于「同一任务同一天只提醒一次」。"""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str | None] = mapped_column(String(150), unique=True)
