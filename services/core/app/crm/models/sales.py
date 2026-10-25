"""商机、报价、报价明细、合同、提成。金额单位：分。"""

import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import OwnedMixin, TimestampMixin


class Opportunity(OwnedMixin, Base):
    __tablename__ = "opportunities"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(20), default="lead", index=True)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    win_rate: Mapped[int] = mapped_column(Integer, default=10)  # 百分比 0~100
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    product_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_lines.id"), nullable=True
    )


class Quote(OwnedMixin, Base):
    __tablename__ = "quotes"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    pack: Mapped[str] = mapped_column(String(50))
    tier: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    total_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    total_price: Mapped[int] = mapped_column(BigInteger, default=0)
    margin_rate: Mapped[float] = mapped_column(Float, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual / agent


class QuoteItem(TimestampMixin, Base):
    __tablename__ = "quote_items"

    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotes.id"), index=True)
    sku: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    qty: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[int] = mapped_column(BigInteger)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(20))  # hardware / software / service


class Contract(OwnedMixin, Base):
    __tablename__ = "contracts"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotes.id"), nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    paid_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")


class Commission(OwnedMixin, Base):
    __tablename__ = "commissions"

    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    estimated: Mapped[int] = mapped_column(BigInteger, default=0)
    confirmed: Mapped[int] = mapped_column(BigInteger, default=0)
