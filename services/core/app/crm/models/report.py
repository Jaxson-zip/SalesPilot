"""销售日报：系统按当天的实际操作生成草稿，本人修改后提交；主管看团队提交情况和周汇总。"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class DailyReport(TimestampMixin, Base):
    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("user_id", "report_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # 当天的数字（提交时快照）
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft / submitted
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
