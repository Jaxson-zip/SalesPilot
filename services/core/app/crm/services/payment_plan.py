"""回款计划计算（B9，纯函数）：按标准比例拆期、把实收按期次顺序分摊、判断逾期。

分摊规则：客户的回款先冲最早一期，冲满再冲下一期（与财务核销顺序一致）；
某期到期日已过且没有收齐 → 逾期，逾期天数从到期日起算。
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.rules.loader import PaymentStage

PlanStatus = Literal["paid", "partial", "overdue", "pending"]


@dataclass(frozen=True)
class PlanInput:
    name: str
    amount: int
    due_date: date


@dataclass(frozen=True)
class PlanState:
    name: str
    amount: int
    due_date: date
    paid: int
    status: PlanStatus
    overdue_days: int


def split_amount(total: int, ratios: list[float]) -> list[int]:
    """按比例拆分金额（分）；四舍五入的差额放到最后一期，保证合计等于合同金额。"""
    parts = [round(total * r) for r in ratios[:-1]]
    return [*parts, total - sum(parts)]


def default_plan(amount: int, signed_on: date, stages: list[PaymentStage]) -> list[PlanInput]:
    amounts = split_amount(amount, [s.ratio for s in stages])
    return [
        PlanInput(s.name, a, signed_on + timedelta(days=s.due_days))
        for s, a in zip(stages, amounts, strict=True)
    ]


def allocate(plans: list[PlanInput], paid_total: int, today: date) -> list[PlanState]:
    remaining = paid_total
    out: list[PlanState] = []
    for p in plans:
        paid = min(p.amount, max(remaining, 0))
        remaining -= paid
        if paid >= p.amount:
            status: PlanStatus = "paid"
        elif p.due_date < today:
            status = "overdue"
        else:
            status = "partial" if paid > 0 else "pending"
        overdue = (today - p.due_date).days if status == "overdue" else 0
        out.append(PlanState(p.name, p.amount, p.due_date, paid, status, overdue))
    return out


def next_due(states: list[PlanState]) -> PlanState | None:
    """下一期要收的款：第一期没有收齐的。"""
    return next((s for s in states if s.status != "paid"), None)
