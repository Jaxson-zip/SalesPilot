"""开票历史

invoice_events：申请开票、登记开票、作废各记一条（只增不改）。作废会清空回款计划期次上的
发票字段，原发票号码、日期、操作人和作废原因留在这里，重新开票后也能追查。

Revision ID: 0028_invoice_events
Revises: 0027_snapshots_counters
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_invoice_events"
down_revision: str | None = "0027_snapshots_counters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("plan_name", sa.String(30), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("invoice_type", sa.String(20), nullable=True),
        sa.Column("invoice_no", sa.String(50), nullable=True),
        sa.Column("invoiced_on", sa.Date(), nullable=True),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_invoice_events_contract_id", "invoice_events", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_events_contract_id", "invoice_events")
    op.drop_table("invoice_events")
