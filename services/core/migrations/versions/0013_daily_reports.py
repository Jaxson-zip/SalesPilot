"""daily_reports：销售日报

Revision ID: 0013_daily_reports
Revises: 0012_competitors
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_daily_reports"
down_revision: str | None = "0012_competitors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("stats", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "report_date"),
    )


def downgrade() -> None:
    op.drop_table("daily_reports")
