"""users 账号体系：登录名、密码哈希、启用状态、首次登录改密、token 版本、最后登录时间

演示用户补上登录名和初始密码（DEMO_PASSWORD，默认 demo2026），老库升级后可以直接用账号密码登录。

Revision ID: 0019_user_accounts
Revises: 0018_payment_plan_invoice
Create Date: 2026-10-29
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.common.passwords import hash_password
from app.crm.services.demo import DEMO_LOGINS

revision: str = "0019_user_accounts"
down_revision: str | None = "0018_payment_plan_invoice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(50), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.add_column("users", sa.Column("password_hash", sa.String(200), nullable=True))
    op.add_column(
        "users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    password = hash_password(os.environ.get("DEMO_PASSWORD") or "demo2026")
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("username", sa.String()),
        sa.column("password_hash", sa.String()),
    )
    for user_id, username in DEMO_LOGINS.items():
        op.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(username=username, password_hash=password)
        )


def downgrade() -> None:
    for column in (
        "last_login_at", "token_version", "must_change_password", "active", "password_hash",
    ):  # fmt: skip
        op.drop_column("users", column)
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
