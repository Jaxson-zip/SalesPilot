"""业绩目标：主管给本团队成员设每月签约额目标，各角色看完成情况。

- 完成额 = 当月新签合同金额（按合同负责人），与工作台「本月成交」同一口径。
- 预测 = 预计当月成交的进行中商机「金额 × 赢率」之和，帮助判断还差多少。
- 销售只看自己；主管看本团队并可修改；管理员看全公司（只读）。
- 团队目标 = 成员目标之和，没有单独的团队目标。
"""

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, delete, false, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_role
from app.common.scope import View, apply_scope
from app.crm.models import Contract, Opportunity, SalesTarget, Team, User
from app.crm.schemas.common import UserBrief
from app.crm.schemas.opportunity import FINAL_STAGES
from app.rules.crm_calc import LOCAL_TZ

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
# 可以设置的月份范围：前后各 12 个月
MONTH_WINDOW = 12
MAX_AMOUNT = 10**13  # 1000 亿元（分）


class TargetRow(BaseModel):
    user: UserBrief
    role: Role
    team_name: str | None = None
    active: bool = True
    target: int | None = None  # 没设目标为 null
    achieved: int = 0  # 当月新签合同金额
    contracts: int = 0
    forecast: int = 0  # 预计当月成交的进行中商机，金额 × 赢率
    rate: float | None = None  # achieved / target


class TargetTotal(BaseModel):
    target: int | None = None
    achieved: int = 0
    forecast: int = 0
    rate: float | None = None


class TargetBoard(BaseModel):
    month: str  # YYYY-MM
    editable: bool  # 主管看本团队
    time_progress: float  # 当月时间进度 0～1（已过去的月为 1，未来的月为 0）
    total: TargetTotal
    rows: list[TargetRow]


class TargetItem(BaseModel):
    user_id: uuid.UUID
    amount: int | None = Field(default=None, ge=0, le=MAX_AMOUNT)  # null 表示清除


class TargetUpdate(BaseModel):
    items: list[TargetItem] = Field(max_length=200)


def parse_month(text: str | None, now: datetime | None = None) -> date:
    current = (now or datetime.now(UTC)).astimezone(LOCAL_TZ).date().replace(day=1)
    if not text:
        return current
    m = _MONTH.match(text)
    if not m:
        raise BizError(ErrorCode.VALIDATION, "月份格式是 YYYY-MM")
    month = date(int(m.group(1)), int(m.group(2)), 1)
    diff = (month.year - current.year) * 12 + month.month - current.month
    if abs(diff) > MONTH_WINDOW:
        raise BizError(ErrorCode.VALIDATION, f"只能查看前后 {MONTH_WINDOW} 个月的目标")
    return month


def _next(month: date) -> date:
    return (month + timedelta(days=32)).replace(day=1)


def _bounds(month: date) -> tuple[datetime, datetime]:
    start = datetime.combine(month, datetime.min.time(), LOCAL_TZ)
    return start, datetime.combine(_next(month), datetime.min.time(), LOCAL_TZ)


def _time_progress(month: date, now: datetime | None = None) -> float:
    start, end = _bounds(month)
    current = now or datetime.now(UTC)
    if current >= end:
        return 1.0
    if current <= start:
        return 0.0
    return round((current - start) / (end - start), 4)


def _rate(achieved: int, target: int | None) -> float | None:
    return round(achieved / target, 4) if target else None


def _grouped(db: Session, stmt: Select[Any]) -> dict[uuid.UUID, tuple[int, int]]:
    return {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in db.execute(stmt).all() if r[0]}


def _members(db: Session, user: CurrentUser, active_ids: set[uuid.UUID]) -> list[User]:
    """要列出的人：销售只有自己；主管是本团队销售和主管；管理员是全公司的。
    停用的成员只在当月有目标或业绩时列出。"""
    stmt = select(User).where(User.role.in_([Role.SALES.value, Role.MANAGER.value]))
    if user.role is Role.SALES:
        stmt = stmt.where(User.id == user.id)
    elif user.role is Role.MANAGER:
        stmt = stmt.where(User.team_id == user.team_id) if user.team_id else stmt.where(false())
    users = db.scalars(stmt.order_by(User.role.desc(), User.name)).all()
    return [u for u in users if u.active or u.id in active_ids or u.id == user.id]


def board(db: Session, user: CurrentUser, month_text: str | None) -> TargetBoard:
    month = parse_month(month_text)
    start, end = _bounds(month)
    view = View.TEAM if user.role is Role.MANAGER else None
    targets = dict(
        db.execute(
            apply_scope(
                select(SalesTarget.owner_id, SalesTarget.amount).where(SalesTarget.month == month),
                SalesTarget,
                user,
                view,
            )
        ).all()
    )
    signed = _grouped(
        db,
        apply_scope(
            select(Contract.owner_id, func.count(), func.sum(Contract.amount))
            .where(Contract.created_at >= start, Contract.created_at < end)
            .group_by(Contract.owner_id),
            Contract,
            user,
            view,
        ),
    )
    weighted = func.sum(Opportunity.amount * Opportunity.win_rate / 100)
    forecast = _grouped(
        db,
        apply_scope(
            select(Opportunity.owner_id, func.count(), weighted)
            .where(
                Opportunity.stage.not_in(FINAL_STAGES),
                Opportunity.expected_close_date >= month,
                Opportunity.expected_close_date < _next(month),
            )
            .group_by(Opportunity.owner_id),
            Opportunity,
            user,
            view,
        ),
    )
    members = _members(db, user, set(targets) | set(signed))
    teams = dict(db.execute(select(Team.id, Team.name)).all())
    rows = []
    for m in members:
        count, achieved = signed.get(m.id, (0, 0))
        target = targets.get(m.id)
        rows.append(
            TargetRow(
                user=UserBrief(id=m.id, name=m.name),
                role=Role(m.role),
                team_name=teams.get(m.team_id) if m.team_id else None,
                active=m.active,
                target=target,
                achieved=achieved,
                contracts=count,
                forecast=forecast.get(m.id, (0, 0))[1],
                rate=_rate(achieved, target),
            )
        )
    set_targets = [r.target for r in rows if r.target is not None]
    total_target = sum(set_targets) if set_targets else None
    total_achieved = sum(r.achieved for r in rows)
    return TargetBoard(
        month=f"{month:%Y-%m}",
        editable=user.role is Role.MANAGER and user.team_id is not None,
        time_progress=_time_progress(month),
        total=TargetTotal(
            target=total_target,
            achieved=total_achieved,
            forecast=sum(r.forecast for r in rows),
            rate=_rate(total_achieved, total_target),
        ),
        rows=rows,
    )


def update(db: Session, user: CurrentUser, month_text: str, body: TargetUpdate) -> TargetBoard:
    """主管批量设置本团队成员的月目标（amount 为 null 清除）。"""
    ensure_role(user, Role.MANAGER, "业绩目标由销售主管设置")
    month = parse_month(month_text)
    ids = {i.user_id for i in body.items}
    members = {
        u.id: u
        for u in db.scalars(
            select(User).where(
                User.id.in_(ids),
                User.team_id == user.team_id,
                or_(User.role == Role.SALES.value, User.role == Role.MANAGER.value),
            )
        )
    }
    outsiders = ids - set(members)
    if outsiders:
        raise BizError(ErrorCode.VALIDATION, "只能给本团队的成员设置目标")
    for item in body.items:
        if item.amount is None:
            db.execute(
                delete(SalesTarget).where(
                    SalesTarget.owner_id == item.user_id, SalesTarget.month == month
                )
            )
            continue
        values = {"amount": item.amount, "team_id": user.team_id, "updated_by": user.id}
        stmt = insert(SalesTarget).values(
            id=uuid.uuid4(), owner_id=item.user_id, month=month, **values
        )
        db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_sales_targets_owner_month",
                set_={**values, "updated_at": func.now()},
            )
        )
    db.flush()
    return board(db, user, month_text)


def month_target(db: Session, user: CurrentUser, view: View | None) -> int | None:
    """工作台用：当前范围内本月目标之和；没人设目标返回 None。"""
    month = parse_month(None)
    stmt = select(func.count(), func.sum(SalesTarget.amount)).where(SalesTarget.month == month)
    count, total = db.execute(apply_scope(stmt, SalesTarget, user, view)).one()
    return int(total) if count else None
