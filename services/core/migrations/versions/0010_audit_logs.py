"""audit_logs：操作日志（网页写操作、AI 写操作、查看联系人电话、导出）

Revision ID: 0010_audit_logs
Revises: 0009_config_overrides
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_audit_logs"
down_revision: str | None = "0009_config_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("user_name", sa.String(50), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("source", sa.String(10), nullable=False, server_default="web"),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("path", sa.String(300), nullable=True),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_team_id", "audit_logs", ["team_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
