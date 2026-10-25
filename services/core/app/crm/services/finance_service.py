"""合同、提成、报销、审批 service。

已实现：estimate_commission、precheck_expense（纯规则计算）。
TODO: 合同列表与回款、报销提交（submitted / pending_approval + approval 记录）、审批通过与驳回。
"""

import uuid

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import not_implemented
from app.crm.schemas.finance import CommissionEstimateIn, ExpenseCreate
from app.rules import (
    CommissionLine,
    CommissionResult,
    ExpenseCheck,
    calc_commission,
    check_expense_policy,
)


def estimate_commission(data: CommissionEstimateIn) -> CommissionResult:
    lines = [CommissionLine(category=line.category, amount=line.amount) for line in data.lines]
    return calc_commission(lines, data.margin_rate, data.paid_ratio)


def precheck_expense(data: ExpenseCreate) -> ExpenseCheck:
    return check_expense_policy(data.amount, data.headcount, data.type)


def submit_expense(db: Session, user: CurrentUser, data: ExpenseCreate) -> dict[str, object]:
    # TODO: 校验客户 / 商机可见性 → precheck_expense → 写 expenses（幂等键）→ 超标时建审批
    raise not_implemented("submit_expense")


def decide_approval(
    db: Session, user: CurrentUser, approval_id: uuid.UUID, decision: str
) -> dict[str, object]:
    # TODO: 仅 manager；更新审批状态并联动报价单 / 报销单状态
    raise not_implemented("decide_approval")
