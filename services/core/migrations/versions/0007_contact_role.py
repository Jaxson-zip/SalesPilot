"""B7: contacts.role（联系人角色：决策人 / 影响者 / 技术把关 / 采购财务 / 使用者）

Revision ID: 0007_contact_role
Revises: 0006_expense_details
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_contact_role"
down_revision: str | None = "0006_expense_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("role", sa.String(20), nullable=True))
    op.execute("UPDATE contacts SET role = 'decision_maker' WHERE is_decision_maker")


def downgrade() -> None:
    op.drop_column("contacts", "role")
