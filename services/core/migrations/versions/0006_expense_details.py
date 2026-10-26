"""v4: expenses.details（差旅交通行程 / 住宿城市与入住离店日期）

Revision ID: 0006_expense_details
Revises: 0005_v3
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_expense_details"
down_revision: str | None = "0005_v3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("details", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "details")
