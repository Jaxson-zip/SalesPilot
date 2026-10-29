"""定时任务：scheduled_jobs（开关、运行时间、参数）与 job_runs（运行记录，(job, run_key) 唯一）

Revision ID: 0020_scheduled_jobs
Revises: 0019_user_accounts
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_scheduled_jobs"
down_revision: str | None = "0019_user_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("run_at", sa.Time(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job", sa.String(40), nullable=False, index=True),
        sa.Column("run_key", sa.String(60), nullable=False),
        sa.Column("trigger", sa.String(10), nullable=False),
        sa.Column("triggered_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="running"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job", "run_key", name="uq_job_runs_job_run_key"),
    )


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("scheduled_jobs")
