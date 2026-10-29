"""opportunities.requirement：出方案时 AI 拆出的需求清单（JSONB），跨会话保存

Revision ID: 0017_opportunity_requirement
Revises: 0016_software_outsourcing
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_opportunity_requirement"
down_revision: str | None = "0016_software_outsourcing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("requirement", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunities", "requirement")
