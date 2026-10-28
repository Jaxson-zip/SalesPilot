"""业务单号：<前缀>-<年份>-<三位序号>，例如 Q-2026-007、C-2026-001、E-2026-012。

序号取当年已有单号的最大值 + 1（不按行数计数，删除记录后也不会撞号）。
"""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session


def format_code(prefix: str, year: int, seq: int) -> str:
    return f"{prefix}-{year}-{seq:03d}"


def parse_seq(code: str | None, prefix: str, year: int) -> int:
    """从单号中取序号；格式不符时返回 0。"""
    head = f"{prefix}-{year}-"
    if not code or not code.startswith(head):
        return 0
    tail = code[len(head) :]
    return int(tail) if tail.isdigit() else 0


def next_code(db: Session, column: InstrumentedAttribute[Any], prefix: str) -> str:
    year = datetime.now(UTC).year
    head = f"{prefix}-{year}-"
    codes = db.scalars(select(column).where(column.like(f"{head}%"))).all()
    seq = max((parse_seq(c, prefix, year) for c in codes), default=0)
    return format_code(prefix, year, seq + 1)


LOCAL_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def local_today(now: datetime | None = None) -> date:
    """北京时间的今天（回款计划判断逾期用）。"""
    return (now or datetime.now(UTC)).astimezone(LOCAL_TZ).date()


def month_start(now: datetime | None = None) -> datetime:
    """本月 1 日 0 点（北京时间），用于工作台「本月」口径。"""
    current = (now or datetime.now(UTC)).astimezone(LOCAL_TZ)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
