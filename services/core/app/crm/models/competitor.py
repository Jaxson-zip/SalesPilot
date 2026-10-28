"""竞品战卡：管理员维护，销售在商机里标注遇到的竞品，现场查应对话术。"""

from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class Competitor(TimestampMixin, Base):
    __tablename__ = "competitors"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)  # 客户口中的叫法，用于搜索
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # 一句话定位
    strengths: Mapped[list[str]] = mapped_column(JSONB, default=list)  # 他们的优势
    weaknesses: Mapped[list[str]] = mapped_column(JSONB, default=list)  # 他们的弱点
    win_tactics: Mapped[list[str]] = mapped_column(JSONB, default=list)  # 我们怎么赢
    # 常见说法与应对：[{"say": 客户 / 竞品的说法, "respond": 我们的回应}]
    objections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
