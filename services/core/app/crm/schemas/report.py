"""销售日报的入参出参（服务层见 app/crm/services/report_service.py）。"""

import datetime as dt
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DailyStats(BaseModel):
    followups: int = 0
    quotes: int = 0  # 新建 / 提交报价
    stage_changes: int = 0
    tasks_done: int = 0
    ai_actions: int = 0  # 通过 AI 工作台完成的操作


class DailyFacts(BaseModel):
    stats: DailyStats = DailyStats()
    actions: list[str] = Field(default_factory=list)  # 「新建报价「xx」」
    followups: list[str] = Field(default_factory=list)  # 「客户：内容」
    tasks_done: list[str] = Field(default_factory=list)
    tomorrow: list[str] = Field(default_factory=list)  # 明天到期的任务


class DailyReportOut(BaseModel):
    date: date
    status: Literal["none", "draft", "submitted"]
    content: str = ""
    submitted_at: datetime | None = None
    facts: DailyFacts


class DailyReportIn(BaseModel):
    date: date
    content: str = Field(min_length=1, max_length=5000)
    submit: bool = False


class DraftIn(BaseModel):
    date: dt.date | None = None  # 字段名与类型同名：默认值会先绑定，必须写全名


class DraftOut(BaseModel):
    source: Literal["ai", "template"]
    content: str


class TeamMemberReport(BaseModel):
    user_id: uuid.UUID
    name: str
    status: Literal["none", "draft", "submitted"]
    content: str | None = None  # 只有提交后主管才看得到内容
    submitted_at: datetime | None = None
    stats: DailyStats


class TeamDailyOut(BaseModel):
    date: date
    submitted: int
    total: int
    members: list[TeamMemberReport]


class SummaryIn(BaseModel):
    days: int = Field(default=7, ge=1, le=31)


class SummaryOut(BaseModel):
    source: Literal["ai", "template"]
    date_from: date
    date_to: date
    content: str


class RemindIn(BaseModel):
    date: dt.date | None = None
