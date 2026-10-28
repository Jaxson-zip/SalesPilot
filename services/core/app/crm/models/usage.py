"""AI 调用用量：每次大模型调用一行（谁、哪个功能、哪个模型、多少 token），用于成本统计。"""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class AiUsage(TimestampMixin, Base):
    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    feature: Mapped[str] = mapped_column(String(30), index=True)  # AI 工作台 / 日报草稿 / …
    model: Mapped[str] = mapped_column(String(80))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
