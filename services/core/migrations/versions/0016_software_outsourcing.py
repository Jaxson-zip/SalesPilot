"""新增产品线「软件定制开发」（行业包 software_outsourcing）

Revision ID: 0016_software_outsourcing
Revises: 0015_ai_usage
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_software_outsourcing"
down_revision: str | None = "0015_ai_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 与 seed/data.py 的 PL_SOFTWARE 相同（demo_id("product_line:software")）
PL_SOFTWARE = "148d8c17-01a1-57da-a933-0dae47d3f38f"


def upgrade() -> None:
    op.execute(
        "INSERT INTO product_lines (id, name, pack, enabled, created_at, updated_at) "
        f"VALUES ('{PL_SOFTWARE}', '软件定制开发', 'software_outsourcing', true, now(), now()) "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM product_lines WHERE id = '{PL_SOFTWARE}'")
