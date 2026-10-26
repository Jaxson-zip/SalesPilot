"""报销、附件、审批。"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import OwnedMixin


class Expense(OwnedMixin, Base):
    __tablename__ = "expenses"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    type: Mapped[str] = mapped_column(String(30))  # entertainment / transport / hotel / other
    amount: Mapped[int] = mapped_column(BigInteger)
    headcount: Mapped[int] = mapped_column(Integer, default=1)
    participants: Mapped[str | None] = mapped_column(Text)
    occurred_on: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunities.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    policy_check: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)


class Attachment(OwnedMixin, Base):
    __tablename__ = "attachments"

    owner_type: Mapped[str] = mapped_column(String(20))  # expense / quote / customer
    owner_ref_id: Mapped[uuid.UUID] = mapped_column(index=True)  # 规范中的 owner_id（被挂载对象）
    kind: Mapped[str] = mapped_column(String(20), default="other")  # invoice / receipt / other
    file_name: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(300))


class Approval(OwnedMixin, Base):
    __tablename__ = "approvals"

    target_type: Mapped[str] = mapped_column(String(20))  # quote / expense
    target_id: Mapped[uuid.UUID] = mapped_column(index=True)
    reason: Mapped[str] = mapped_column(Text)
    ai_suggestion: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
