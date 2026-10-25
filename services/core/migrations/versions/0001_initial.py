"""org and knowledge base

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 向量维度需与 Embedding 模型一致；换模型需新迁移并重建索引
EMBEDDING_DIMS = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _create_product_lines()
    _create_teams()
    _create_users()
    _create_kb_chunks()
    # teams.manager_id 与 users 互相引用，建完 users 后再加外键
    op.create_foreign_key("fk_teams_manager_id", "teams", "users", ["manager_id"], ["id"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_chunks_embedding_hnsw "
        "ON kb_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _create_product_lines() -> None:
    op.create_table(
        "product_lines",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("pack", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def _create_teams() -> None:
    op.create_table(
        "teams",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        sa.Column("default_product_line_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["default_product_line_id"],
            ["product_lines.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)


def _create_kb_chunks() -> None:
    op.create_table(
        "kb_chunks",
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("pack", sa.String(length=50), nullable=True),
        sa.Column("doc_name", sa.String(length=200), nullable=False),
        sa.Column("section", sa.String(length=300), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMS), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index(op.f("ix_kb_chunks_scope"), "kb_chunks", ["scope"], unique=False)


def downgrade() -> None:
    op.drop_constraint("fk_teams_manager_id", "teams", type_="foreignkey")
    for table in ["kb_chunks", "users", "teams", "product_lines"]:
        op.drop_table(table)
