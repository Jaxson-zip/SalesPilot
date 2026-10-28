"""integrations：外部集成配置（企业微信群机器人）

Revision ID: 0014_integrations
Revises: 0013_daily_reports
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_integrations"
down_revision: str | None = "0013_daily_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("kind", sa.String(20), nullable=False, unique=True),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("recent", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("updated_by", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("integrations")
