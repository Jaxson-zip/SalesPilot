"""AI 回复的点赞 / 点踩：ai_feedback

Revision ID: 0024_ai_feedback
Revises: 0023_prd_client_costs
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_ai_feedback"
down_revision: str | None = "0023_prd_client_costs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("thread_id", sa.String(100), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False, server_default="work"),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "thread_id", "message_index"),
    )
    op.create_index("ix_ai_feedback_user_id", "ai_feedback", ["user_id"])
    op.create_index("ix_ai_feedback_thread_id", "ai_feedback", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_feedback_thread_id", "ai_feedback")
    op.drop_index("ix_ai_feedback_user_id", "ai_feedback")
    op.drop_table("ai_feedback")
