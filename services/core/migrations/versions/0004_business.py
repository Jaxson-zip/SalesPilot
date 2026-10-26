"""business modules: lost_reason / closed_at, approval comment / decided_at,
contract customer_id, followup occurred_at

Revision ID: 0004_business
Revises: 0003_quotes
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_business"
down_revision: str | None = "0003_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("lost_reason", sa.Text(), nullable=True))
    op.add_column(
        "opportunities", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("approvals", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("approvals", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contracts", sa.Column("customer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_contracts_customer_id", "contracts", "customers", ["customer_id"], ["id"]
    )
    op.create_index(op.f("ix_contracts_customer_id"), "contracts", ["customer_id"], unique=False)
    op.add_column("followups", sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("followups", "occurred_at")
    op.drop_index(op.f("ix_contracts_customer_id"), table_name="contracts")
    op.drop_constraint("fk_contracts_customer_id", "contracts", type_="foreignkey")
    op.drop_column("contracts", "customer_id")
    op.drop_column("approvals", "decided_at")
    op.drop_column("approvals", "comment")
    op.drop_column("opportunities", "closed_at")
    op.drop_column("opportunities", "lost_reason")
