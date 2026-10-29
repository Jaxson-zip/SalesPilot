"""知识库切块（pgvector）与 Agent 会话列表。"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.config import get_settings
from app.common.db import Base
from app.crm.models.base import TimestampMixin

EMBEDDING_DIMS = get_settings().embedding_dims


class KbChunk(TimestampMixin, Base):
    __tablename__ = "kb_chunks"

    scope: Mapped[str] = mapped_column(String(50), index=True)  # company / pack:<id>
    pack: Mapped[str | None] = mapped_column(String(50))
    doc_name: Mapped[str] = mapped_column(String(200))
    section: Mapped[str | None] = mapped_column(String(300))
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMS))


class AgentThread(TimestampMixin, Base):
    __tablename__ = "agent_threads"

    thread_id: Mapped[str] = mapped_column(String(100), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunities.id"))
    # 会话模式：work 做方案（默认）/ learn 学习问答；新建时确定
    mode: Mapped[str] = mapped_column(String(10), default="work", server_default="work")
