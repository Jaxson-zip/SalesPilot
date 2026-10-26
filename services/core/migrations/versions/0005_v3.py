"""v3: tasks, notifications, quote discount_rate, structured expense participants

Revision ID: 0005_v3
Revises: 0004_business
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_v3"
down_revision: str | None = "0004_business"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    ]


def _create_tasks() -> None:
    op.create_table(
        "tasks",
        *_timestamps(),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
    )
    for col in ("owner_id", "team_id", "due_at", "done", "subject_id", "customer_id"):
        op.create_index(f"ix_tasks_{col}", "tasks", [col])


def _create_notifications() -> None:
    op.create_table(
        "notifications",
        *_timestamps(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(150), nullable=True, unique=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])


# 已有报价：按明细原价与成交价回填整单折扣率
BACKFILL_DISCOUNT = """
UPDATE quotes q SET discount_rate = round((1 - q.total_price::numeric / s.list_price), 4)
FROM (SELECT quote_id, sum(unit_price * qty) AS list_price FROM quote_items GROUP BY quote_id) s
WHERE s.quote_id = q.id AND s.list_price > 0 AND q.total_price < s.list_price
"""


def upgrade() -> None:
    _create_tasks()
    _create_notifications()
    op.add_column(
        "quotes", sa.Column("discount_rate", sa.Float(), server_default="0", nullable=False)
    )
    op.execute(BACKFILL_DISCOUNT)
    op.add_column("expenses", sa.Column("contact_ids", sa.ARRAY(sa.Uuid()), nullable=True))
    op.add_column("expenses", sa.Column("colleague_ids", sa.ARRAY(sa.Uuid()), nullable=True))
    op.add_column("expenses", sa.Column("extra_guests", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "extra_guests")
    op.drop_column("expenses", "colleague_ids")
    op.drop_column("expenses", "contact_ids")
    op.drop_column("quotes", "discount_rate")
    op.drop_table("notifications")
    op.drop_table("tasks")
