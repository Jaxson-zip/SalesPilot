"""报价分享链接：quote_shares

Revision ID: 0025_quote_shares
Revises: 0024_ai_feedback
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_quote_shares"
down_revision: str | None = "0024_ai_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quote_shares",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quote_id", sa.Uuid(), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_quote_shares_quote_id", "quote_shares", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_quote_shares_quote_id", "quote_shares")
    op.drop_table("quote_shares")
