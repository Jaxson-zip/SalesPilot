"""补关已输单商机下的报价和待办

输单自动关闭报价（opportunity_close.close_lost）是 0029 之后才加的，之前输单的商机下
还留着「已审批」「已发送」的报价和未完成的待办：界面上能看到发送入口，点了才被拦下。
这里按 close_lost 的口径补一次：报价改为已关闭，待审批的报价审批单驳回，待办标记完成。

Revision ID: 0030_close_lost_quotes
Revises: 0029_quote_revisions
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_close_lost_quotes"
down_revision: str | None = "0029_quote_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTE = "商机已输单，自动关闭"
OPEN_LOST_QUOTES = """
    SELECT q.id FROM quotes q JOIN opportunities o ON o.id = q.opportunity_id
    WHERE o.stage = 'lost' AND q.status IN ('draft', 'pending_approval', 'approved', 'sent')
"""


# 顺序：先驳回审批单（要按「还没关闭的报价」找），再关报价，最后完成待办
STATEMENTS = [
    sa.text(
        "UPDATE approvals SET status = 'rejected', comment = :note, decided_at = now() "
        "WHERE target_type = 'quote' AND status = 'pending' "
        f"AND target_id IN ({OPEN_LOST_QUOTES})"
    ).bindparams(note=NOTE),
    sa.text(f"UPDATE quotes SET status = 'closed' WHERE id IN ({OPEN_LOST_QUOTES})"),
    sa.text(
        "UPDATE tasks SET done = true, done_at = now(), "
        "note = concat_ws(E'\n', NULLIF(note, ''), :note) "
        "WHERE done = false AND subject_type = 'opportunity' "
        "AND subject_id IN (SELECT id FROM opportunities WHERE stage = 'lost')"
    ).bindparams(note=NOTE),
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    # 数据修正，不可逆：原来的状态没有保存
    pass
