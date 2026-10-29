"""PRD 规格书与客户自付费用：opportunities.prd、quotes.client_costs

Revision ID: 0023_prd_client_costs
Revises: 0022_agent_thread_mode
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_prd_client_costs"
down_revision: str | None = "0022_agent_thread_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("prd", postgresql.JSONB(), nullable=True))
    op.add_column(
        "quotes",
        sa.Column("client_costs", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("quotes", "client_costs")
    op.drop_column("opportunities", "prd")
