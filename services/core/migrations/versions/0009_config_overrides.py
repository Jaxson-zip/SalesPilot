"""config_overrides：管理员在网页上改过的规则 / 行业包参数 / 产品价格（文件是默认值）

Revision ID: 0009_config_overrides
Revises: 0008_payment_plans
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_config_overrides"
down_revision: str | None = "0008_payment_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "config_overrides",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("scope", "key", name="uq_config_overrides_scope_key"),
    )


def downgrade() -> None:
    op.drop_table("config_overrides")
