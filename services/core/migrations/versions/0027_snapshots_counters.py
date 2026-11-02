"""报价快照、回款防重复、单号计数器

- quotes.snapshot：提交审批时固化给客户看的项目范围和条款，之后改需求、改条款模板不影响这一版。
- payments.idempotency_key：同一次登记的重试（第一次已入账但页面没收到响应）不会再记一笔。
- code_counters：单号按「类型 + 年份」原子分配，多人同时新建不会撞号。

Revision ID: 0027_snapshots_counters
Revises: 0026_payments
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0027_snapshots_counters"
down_revision: str | None = "0026_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("snapshot", JSONB(), nullable=True))
    op.add_column("payments", sa.Column("idempotency_key", sa.String(100), nullable=True))
    op.create_unique_constraint("uq_payments_idempotency_key", "payments", ["idempotency_key"])
    op.create_table(
        "code_counters",
        sa.Column("prefix", sa.String(10), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("seq", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("code_counters")
    op.drop_constraint("uq_payments_idempotency_key", "payments")
    op.drop_column("payments", "idempotency_key")
    op.drop_column("quotes", "snapshot")
