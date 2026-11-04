"""跟进记录关联联系人

followups.contact_id：这次跟进联系的是客户方哪位。联系人删除后置空，跟进内容保留。

Revision ID: 0031_followup_contact
Revises: 0030_close_lost_quotes
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_followup_contact"
down_revision: str | None = "0030_close_lost_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("followups", sa.Column("contact_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_followups_contact_id", "followups", "contacts", ["contact_id"], ["id"],
        ondelete="SET NULL",
    )  # fmt: skip


def downgrade() -> None:
    op.drop_constraint("fk_followups_contact_id", "followups", type_="foreignkey")
    op.drop_column("followups", "contact_id")
