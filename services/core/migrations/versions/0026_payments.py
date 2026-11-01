"""回款记录：payments（到账日期、流水号、备注、冲正）

已有合同的 paid_amount 补一条「迁移前登记」的历史记录，保证记录合计 = 已回款。

Revision ID: 0026_payments
Revises: 0025_quote_shares
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_payments"
down_revision: str | None = "0025_quote_shares"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("reference_no", sa.String(64), nullable=True),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("reversal_of", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_payments_contract_id", "payments", ["contract_id"])
    op.create_index("ix_payments_reversal_of", "payments", ["reversal_of"])
    op.execute(
        """
        INSERT INTO payments (id, contract_id, amount, received_on, note, created_at, updated_at)
        SELECT gen_random_uuid(), id, paid_amount, updated_at::date,
               '迁移前登记的回款，没有到账明细', now(), now()
        FROM contracts WHERE paid_amount > 0
        """
    )


def downgrade() -> None:
    op.drop_index("ix_payments_reversal_of", "payments")
    op.drop_index("ix_payments_contract_id", "payments")
    op.drop_table("payments")
