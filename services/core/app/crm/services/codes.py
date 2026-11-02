"""业务单号：<前缀>-<年份>-<三位序号>，例如 Q-2026-007、C-2026-001、E-2026-012。

序号由 code_counters 按「前缀 + 年份」原子分配（INSERT … ON CONFLICT DO UPDATE），
多人同时新建不会拿到同一个号；计数器落后于已有单号（迁移前的数据）时从已有最大值往后接。
"""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
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


_NEXT_SEQ = text(
    """
    INSERT INTO code_counters (prefix, year, seq) VALUES (:prefix, :year, :floor + 1)
    ON CONFLICT (prefix, year)
    DO UPDATE SET seq = GREATEST(code_counters.seq, :floor) + 1
    RETURNING seq
    """
)


def next_code(db: Session, column: InstrumentedAttribute[Any], prefix: str) -> str:
    """分配下一个单号；计数器这一行锁到本事务提交，同类单号的并发新建排队拿号。"""
    year = datetime.now(UTC).year
    head = f"{prefix}-{year}-"
    codes = db.scalars(select(column).where(column.like(f"{head}%"))).all()
    floor = max((parse_seq(c, prefix, year) for c in codes), default=0)
    seq = db.scalar(_NEXT_SEQ, {"prefix": prefix, "year": year, "floor": floor})
    return format_code(prefix, year, int(seq))


LOCAL_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def local_today(now: datetime | None = None) -> date:
    """北京时间的今天（回款计划判断逾期用）。"""
    return (now or datetime.now(UTC)).astimezone(LOCAL_TZ).date()


def month_start(now: datetime | None = None) -> datetime:
    """本月 1 日 0 点（北京时间），用于工作台「本月」口径。"""
    current = (now or datetime.now(UTC)).astimezone(LOCAL_TZ)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
