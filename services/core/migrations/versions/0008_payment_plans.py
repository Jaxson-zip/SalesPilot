"""B9: payment_plans（合同回款计划）；已有合同按标准比例 30% / 60% / 10% 补齐计划

Revision ID: 0008_payment_plans
Revises: 0007_contact_role
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_payment_plans"
down_revision: str | None = "0007_contact_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 与 rules.yaml payment.schedule 的默认值一致；迁移里固定写死，不随规则文件变化
_BACKFILL = """
INSERT INTO payment_plans (id, created_at, updated_at, owner_id, team_id,
                           contract_id, seq, name, amount, due_date)
SELECT gen_random_uuid(), now(), now(), c.owner_id, c.team_id, c.id, s.seq, s.name,
       CASE WHEN s.seq = 3 THEN c.amount - round(c.amount * 0.3) - round(c.amount * 0.6)
            ELSE round(c.amount * s.ratio) END,
       (c.created_at AT TIME ZONE 'Asia/Shanghai')::date + s.due_days
FROM contracts c
CROSS JOIN (VALUES (1, '预付款', 0.3, 0), (2, '到货验收款', 0.6, 60), (3, '质保金', 0.1, 425))
     AS s(seq, name, ratio, due_days)
"""


def upgrade() -> None:
    op.create_table(
        "payment_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(30), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
    )
    for col in ("owner_id", "team_id", "contract_id"):
        op.create_index(f"ix_payment_plans_{col}", "payment_plans", [col])
    op.execute(_BACKFILL)


def downgrade() -> None:
    op.drop_table("payment_plans")
