"""操作日志：谁、什么时候、通过网页还是 AI、对什么做了什么、结果如何。只增不改。"""

import uuid
from typing import Any

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)  # 如 customer.update
    label: Mapped[str] = mapped_column(String(60))  # 中文名，如「修改客户」
    source: Mapped[str] = mapped_column(String(10), default="web")  # web / agent
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[int] = mapped_column(Integer, default=200)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
