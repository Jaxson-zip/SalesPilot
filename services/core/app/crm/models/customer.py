"""客户、联系人、跟进、动态。"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import OwnedMixin


class Customer(OwnedMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(200), index=True)
    industry: Mapped[str | None] = mapped_column(String(50))
    level: Mapped[str] = mapped_column(String(1), default="C")  # A / B / C
    size: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(200))
    annual_budget: Mapped[int | None] = mapped_column(BigInteger)  # 分
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)


class Contact(OwnedMixin, Base):
    __tablename__ = "contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(30))
    # is_decision_maker 由 role 派生（role == decision_maker），保留给旧接口
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 见 schemas ContactRole


class Followup(OwnedMixin, Base):
    __tablename__ = "followups"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(20))  # phone / visit / wechat / email / ai
    content: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual / agent


class Activity(OwnedMixin, Base):
    """动态：可见范围跟着 subject（客户 / 商机）走，team_id 用于团队范围过滤。"""

    __tablename__ = "activities"

    subject_type: Mapped[str] = mapped_column(String(20))  # customer/opportunity/quote/expense
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual / agent
    action: Mapped[str] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text)
