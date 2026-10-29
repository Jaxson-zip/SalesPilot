"""AI 会话模式：agent_threads.mode（work 做方案 / learn 学习问答）

Revision ID: 0022_agent_thread_mode
Revises: 0021_sales_targets
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_agent_thread_mode"
down_revision: str | None = "0021_sales_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_threads",
        sa.Column("mode", sa.String(10), nullable=False, server_default="work"),
    )


def downgrade() -> None:
    op.drop_column("agent_threads", "mode")
