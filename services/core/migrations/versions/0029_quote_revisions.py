"""报价修订版本

quotes.revision_of_id：已发送 / 客户拒绝的报价「复制为新版本」时指向原报价。
新版本发送后原报价关闭（状态 closed），两张报价在详情里互相能找到。

Revision ID: 0029_quote_revisions
Revises: 0028_invoice_events
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_quote_revisions"
down_revision: str | None = "0028_invoice_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quotes",
        sa.Column("revision_of_id", sa.Uuid(), sa.ForeignKey("quotes.id"), nullable=True),
    )
    op.create_index("ix_quotes_revision_of_id", "quotes", ["revision_of_id"])


def downgrade() -> None:
    op.drop_index("ix_quotes_revision_of_id", table_name="quotes")
    op.drop_column("quotes", "revision_of_id")
