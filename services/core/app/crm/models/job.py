"""定时任务：每个任务的配置（开关、运行时间、参数）和运行记录。"""

import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base


class ScheduledJob(Base):
    """管理员在网页上改过的配置；没有记录的任务用代码里的默认值。"""

    __tablename__ = "scheduled_jobs"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool]
    run_at: Mapped[time] = mapped_column(Time)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JobRun(Base):
    """一次运行。(job, run_key) 唯一：自动运行的 run_key 是日期，多实例 / 重启也一天只跑一次。"""

    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("job", "run_key", name="uq_job_runs_job_run_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job: Mapped[str] = mapped_column(String(40), index=True)
    run_key: Mapped[str] = mapped_column(String(60))
    trigger: Mapped[str] = mapped_column(String(10))  # auto / manual
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="running")  # running / ok / failed
    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
