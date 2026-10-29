"""业绩目标：sales_targets（每人每月签约额目标，(owner_id, month) 唯一）

Revision ID: 0021_sales_targets
Revises: 0020_scheduled_jobs
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_sales_targets"
down_revision: str | None = "0020_scheduled_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales_targets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("owner_id", "month", name="uq_sales_targets_owner_month"),
    )


def downgrade() -> None:
    op.drop_table("sales_targets")
