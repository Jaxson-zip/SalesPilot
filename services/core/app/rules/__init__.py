"""规则引擎：rules.yaml + 纯函数计算器。价格、毛利、提成、是否超标只能由这里计算。"""

from app.rules.calculators import (
    CommissionLine,
    CommissionResult,
    ExpenseCheck,
    MarginCheck,
    allocate_by_category,
    calc_commission,
    check_discount,
    check_expense_policy,
    check_margin,
    confirm_commission,
    discounted_price,
    paid_ratio_of,
    weighted_amount,
)
from app.rules.loader import RuleSet, load_rules

__all__ = [
    "CommissionLine",
    "CommissionResult",
    "ExpenseCheck",
    "MarginCheck",
    "RuleSet",
    "allocate_by_category",
    "calc_commission",
    "check_discount",
    "check_expense_policy",
    "check_margin",
    "confirm_commission",
    "discounted_price",
    "load_rules",
    "paid_ratio_of",
    "weighted_amount",
]
