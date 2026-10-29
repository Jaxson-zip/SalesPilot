"""payment_plans 开票跟踪：每期开票状态（未开票 / 已申请 / 已开票）、发票类型、号码、开票日期

Revision ID: 0018_payment_plan_invoice
Revises: 0017_opportunity_requirement
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_payment_plan_invoice"
down_revision: str | None = "0017_opportunity_requirement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payment_plans",
        sa.Column("invoice_status", sa.String(20), nullable=False, server_default="none"),
    )
    op.add_column("payment_plans", sa.Column("invoice_type", sa.String(20), nullable=True))
    op.add_column("payment_plans", sa.Column("invoice_no", sa.String(50), nullable=True))
    op.add_column("payment_plans", sa.Column("invoiced_on", sa.Date(), nullable=True))
    op.add_column("payment_plans", sa.Column("invoice_note", sa.String(200), nullable=True))
    op.add_column(
        "payment_plans",
        sa.Column("invoice_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for col in (
        "invoice_requested_at",
        "invoice_note",
        "invoiced_on",
        "invoice_no",
        "invoice_type",
        "invoice_status",
    ):
        op.drop_column("payment_plans", col)
