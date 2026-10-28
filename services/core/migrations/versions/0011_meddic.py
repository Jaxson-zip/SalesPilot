"""opportunities.meddic：MEDDIC 赢单要素（JSONB）

Revision ID: 0011_meddic
Revises: 0010_audit_logs
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_meddic"
down_revision: str | None = "0010_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("meddic", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunities", "meddic")
