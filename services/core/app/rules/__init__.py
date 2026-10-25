"""规则引擎：rules.yaml + 纯函数计算器。价格、毛利、提成、是否超标只能由这里计算。"""

from app.rules.calculators import (
    CommissionLine,
    CommissionResult,
    ExpenseCheck,
    MarginCheck,
    calc_commission,
    check_discount,
    check_expense_policy,
    check_margin,
)
from app.rules.loader import RuleSet, load_rules

__all__ = [
    "CommissionLine",
    "CommissionResult",
    "ExpenseCheck",
    "MarginCheck",
    "RuleSet",
    "calc_commission",
    "check_discount",
    "check_expense_policy",
    "check_margin",
    "load_rules",
]
