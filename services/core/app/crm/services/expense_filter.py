"""报销列表的筛选条件：类型、状态、是否超标、关联商机。"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, Select, false

from app.crm.models import Expense
from app.crm.services.listing import SortKey


@dataclass(frozen=True)
class ExpenseFilter:
    """列表筛选（多选）：类型、状态、是否超标（yes / no）；opportunity_id 只看这个商机的费用。"""

    type: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    over: list[str] = field(default_factory=list)
    sort: SortKey | None = None
    opportunity_id: uuid.UUID | None = None


def over_limit_condition() -> ColumnElement[bool]:
    """超标：有制度校验结果、未通过且超出金额 > 0（与列表项 over_limit 一致）。"""
    return (Expense.policy_check["passed"].as_boolean() == false()) & (
        Expense.policy_check["over_amount"].as_integer() > 0
    )


def apply_filter(stmt: Select[Any], f: ExpenseFilter | None) -> Select[Any]:
    if f is None:
        return stmt
    if f.type:
        stmt = stmt.where(Expense.type.in_(f.type))
    if f.status:
        stmt = stmt.where(Expense.status.in_(f.status))
    if len(set(f.over) & {"yes", "no"}) == 1:
        cond = over_limit_condition()
        stmt = stmt.where(cond if "yes" in f.over else ~cond | Expense.policy_check.is_(None))
    if f.opportunity_id:
        stmt = stmt.where(Expense.opportunity_id == f.opportunity_id)
    return stmt
