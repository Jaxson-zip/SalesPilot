"""AI 回复的点赞 / 点踩：每人对每条回复一行（再点一次取消），主管和管理员按「没帮助」复盘。"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class AiFeedback(TimestampMixin, Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (UniqueConstraint("user_id", "thread_id", "message_index"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    thread_id: Mapped[str] = mapped_column(String(100), index=True)
    # 会话里第几轮（服务端第几条用户消息，从 0 开始）：刷新、重新打开历史后不变
    message_index: Mapped[int] = mapped_column(Integer)
    rating: Mapped[str] = mapped_column(String(10))  # up / down
    mode: Mapped[str] = mapped_column(String(10), default="work")
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
