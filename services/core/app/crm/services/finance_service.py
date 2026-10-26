"""纯规则计算接口：提成估算、报销制度预校验（不落库）。

合同 / 回款见 contract_service，报销见 expense_service，审批见 approval_service。
"""

from app.crm.schemas.finance import CommissionEstimateIn, ExpensePrecheckIn
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


def precheck_expense(data: ExpensePrecheckIn) -> ExpenseCheck:
    details = data.details.model_dump(mode="json", exclude_none=True) if data.details else None
    return check_expense_policy(data.amount, data.headcount, data.type, details=details)
