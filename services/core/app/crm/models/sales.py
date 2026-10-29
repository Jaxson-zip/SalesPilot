"""商机、报价、报价明细、合同、提成。金额单位：分。"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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
    lost_reason: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 进入终态的时间
    # MEDDIC 赢单要素：{key: {status, evidence, updated_at, updated_by}}（meddic_service）
    meddic: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    competitor_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)  # 遇到的竞品
    # 出方案时的需求清单：{pack, data, confirmed, price_low, price_high, questions, ...}
    requirement: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


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
    discount_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")
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
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    paid_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")


class PaymentPlan(OwnedMixin, Base):
    """合同回款计划的一期（B9）。实收按期次顺序分摊，状态由 payment_plan.allocate 计算，不落库。"""

    __tablename__ = "payment_plans"

    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(30))
    amount: Mapped[int] = mapped_column(BigInteger)
    due_date: Mapped[date] = mapped_column(Date)
    # 开票跟踪：none 未开票 / requested 销售已申请 / issued 已开票（主管登记）
    invoice_status: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
    invoice_type: Mapped[str | None] = mapped_column(String(20))  # special 专票 / normal 普票
    invoice_no: Mapped[str | None] = mapped_column(String(50))
    invoiced_on: Mapped[date | None] = mapped_column(Date)
    invoice_note: Mapped[str | None] = mapped_column(String(200))  # 申请时的备注（抬头、税号等）
    invoice_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Commission(OwnedMixin, Base):
    __tablename__ = "commissions"

    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    estimated: Mapped[int] = mapped_column(BigInteger, default=0)
    confirmed: Mapped[int] = mapped_column(BigInteger, default=0)
