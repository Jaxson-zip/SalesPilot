"""AI 用量与成本统计：管理员看全公司，主管看本团队；费用按当前单价估算。"""

from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.crm.models import AiUsage, User
from app.crm.services.codes import LOCAL_TZ, local_today
from app.rules import load_rules

Period = Literal["7d", "30d", "month"]


def tokens_today(db: Session, user_id: Any) -> int:
    start = datetime.combine(local_today(), time.min, tzinfo=LOCAL_TZ)
    stmt = select(func.coalesce(func.sum(AiUsage.prompt_tokens + AiUsage.completion_tokens), 0))
    return int(db.scalar(stmt.where(AiUsage.user_id == user_id, AiUsage.created_at >= start)) or 0)


def ensure_daily_quota(user: CurrentUser) -> None:
    """每人每日 tokens 上限（ai_usage.user_daily_tokens）：发起新的 AI 调用前检查，超过 42901。"""
    limit = load_rules().ai_usage.user_daily_tokens
    if limit <= 0:
        return
    with session_scope() as db:
        used = tokens_today(db, user.id)
    if used >= limit:
        raise BizError(
            ErrorCode.RATE_LIMITED,
            f"今天的 AI 用量已达上限（{limit:,} tokens），明天恢复；如需提高请联系管理员",
            {"rule": "ai_daily_quota", "used": used, "limit": limit},
        )


class UsageRow(BaseModel):
    key: str  # 用户 id / 功能名 / 模型名 / 日期
    label: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost: int  # 分（估算）


class UsageStats(BaseModel):
    period: Period
    date_from: date
    date_to: date
    scope: Literal["company", "team"]
    total: UsageRow
    by_user: list[UsageRow]
    by_feature: list[UsageRow]
    by_model: list[UsageRow]
    by_day: list[UsageRow]
    input_price: float  # 元 / 百万 tokens
    output_price: float
    monthly_budget: int  # 分，0 表示不设预算
    month_cost: int  # 本月至今（同一范围）
    unattributed_calls: int  # 无法归属到人的调用（系统任务）


def _range(period: Period) -> tuple[date, date]:
    today = local_today()
    if period == "month":
        return today.replace(day=1), today
    return today - timedelta(days=6 if period == "7d" else 29), today


def _start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=LOCAL_TZ)


def _cost(p: int, c: int) -> int:
    rules = load_rules().ai_usage
    yuan = (p * rules.input_price_per_million + c * rules.output_price_per_million) / 1_000_000
    return round(yuan * 100)


def _row(key: str, label: str, calls: int, p: int, c: int) -> UsageRow:
    return UsageRow(
        key=key,
        label=label,
        calls=int(calls),
        prompt_tokens=int(p or 0),
        completion_tokens=int(c or 0),
        cost=_cost(int(p or 0), int(c or 0)),
    )


def _scoped(stmt: Select, user: CurrentUser) -> Select:  # type: ignore[type-arg]
    if user.role == Role.MANAGER:
        return stmt.where(AiUsage.team_id == user.team_id)
    return stmt


def _agg(db: Session, user: CurrentUser, start: datetime, end: datetime, *group: Any) -> list[Any]:
    cols = (
        func.count(AiUsage.id),
        func.coalesce(func.sum(AiUsage.prompt_tokens), 0),
        func.coalesce(func.sum(AiUsage.completion_tokens), 0),
    )
    stmt = select(*group, *cols).where(AiUsage.created_at >= start, AiUsage.created_at < end)
    if group:
        stmt = stmt.group_by(*group)
    return list(db.execute(_scoped(stmt, user)).all())


def stats(db: Session, user: CurrentUser, period: Period) -> UsageStats:
    if user.role == Role.SALES:
        raise BizError(ErrorCode.FORBIDDEN, "AI 用量统计仅主管和管理员可以查看")
    d_from, d_to = _range(period)
    start, end = _start(d_from), _start(d_to + timedelta(days=1))

    (calls, p, c), *_ = _agg(db, user, start, end)
    total = _row("total", "合计", calls, p, c)

    names = dict(db.execute(select(User.id, User.name)).all())
    by_user = [
        _row(str(uid) if uid else "-", names.get(uid, "系统任务") if uid else "系统任务", n, pp, cc)
        for uid, n, pp, cc in _agg(db, user, start, end, AiUsage.user_id)
    ]
    by_feature = [
        _row(f, f, n, pp, cc) for f, n, pp, cc in _agg(db, user, start, end, AiUsage.feature)
    ]
    by_model = [_row(m, m, n, pp, cc) for m, n, pp, cc in _agg(db, user, start, end, AiUsage.model)]
    for rows in (by_user, by_feature, by_model):
        rows.sort(key=lambda r: (r.cost, r.prompt_tokens + r.completion_tokens), reverse=True)

    day = func.date(func.timezone("Asia/Shanghai", AiUsage.created_at))
    per_day = {d: (n, pp, cc) for d, n, pp, cc in _agg(db, user, start, end, day)}
    by_day = []
    d = d_from
    while d <= d_to:
        n, pp, cc = per_day.get(d, (0, 0, 0))
        by_day.append(_row(d.isoformat(), f"{d:%m-%d}", n, pp, cc))
        d += timedelta(days=1)

    m_start = _start(local_today().replace(day=1))
    m_end = _start(local_today() + timedelta(days=1))
    (_, mp, mc), *_ = _agg(db, user, m_start, m_end)
    rules = load_rules().ai_usage
    budget = rules.monthly_budget
    if user.role == Role.MANAGER and rules.team_monthly_budget:
        budget = rules.team_monthly_budget
    return UsageStats(
        period=period,
        date_from=d_from,
        date_to=d_to,
        scope="team" if user.role == Role.MANAGER else "company",
        total=total,
        by_user=by_user,
        by_feature=by_feature,
        by_model=by_model,
        by_day=by_day,
        input_price=rules.input_price_per_million,
        output_price=rules.output_price_per_million,
        monthly_budget=budget,
        month_cost=_cost(int(mp), int(mc)),
        unattributed_calls=sum(r.calls for r in by_user if r.key == "-"),
    )
