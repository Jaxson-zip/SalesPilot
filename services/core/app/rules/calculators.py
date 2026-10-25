"""纯函数计算器：毛利、折扣、提成、报销制度校验。金额单位一律为整数「分」。"""

from pydantic import BaseModel

from app.rules.loader import RuleSet, load_rules


class MarginCheck(BaseModel):
    total_cost: int
    total_price: int
    margin_rate: float  # 四舍五入到 4 位小数，例如 0.3120
    floor_rate: float
    passed: bool
    reason: str


class CommissionLine(BaseModel):
    category: str  # hardware / software / service
    amount: int  # 该类别的合同金额（分）


class CommissionResult(BaseModel):
    estimated: int  # 按合同金额估算的提成（分）
    confirmed: int  # 按回款比例确认的提成（分）
    halved: bool
    detail: dict[str, int]


class ExpenseCheck(BaseModel):
    per_person: int
    limit_per_person: int
    over_amount: int
    need_approval: bool
    reason: str


def _rules(rules: RuleSet | None) -> RuleSet:
    return rules if rules is not None else load_rules()


def margin_rate_of(total_cost: int, total_price: int) -> float:
    if total_price <= 0:
        return 0.0
    return round((total_price - total_cost) / total_price, 4)


def check_margin(total_cost: int, total_price: int, rules: RuleSet | None = None) -> MarginCheck:
    if total_cost < 0 or total_price < 0:
        raise ValueError("金额不能为负数")
    floor = _rules(rules).margin.floor_rate
    rate = margin_rate_of(total_cost, total_price)
    passed = total_price > 0 and rate >= floor
    reason = (
        f"毛利 {rate:.1%} ≥ {floor:.0%}"
        if passed
        else f"毛利 {rate:.1%} < {floor:.0%}，需要主管审批或调整配置"
    )
    return MarginCheck(
        total_cost=total_cost,
        total_price=total_price,
        margin_rate=rate,
        floor_rate=floor,
        passed=passed,
        reason=reason,
    )


def check_discount(list_price: int, final_price: int, rules: RuleSet | None = None) -> bool:
    """返回是否在销售折扣权限内（True = 无需审批）。"""
    if list_price <= 0:
        raise ValueError("原价必须大于 0")
    discount = (list_price - final_price) / list_price
    return discount <= _rules(rules).discount.max_rate + 1e-9


def calc_commission(
    lines: list[CommissionLine],
    margin_rate: float,
    paid_ratio: float = 1.0,
    rules: RuleSet | None = None,
) -> CommissionResult:
    """提成 = Σ 类别金额 × 类别比例；毛利低于底线减半；按回款比例确认。"""
    if not 0 <= paid_ratio <= 1:
        raise ValueError("回款比例必须在 0~1 之间")
    cfg = _rules(rules).commission
    halved = margin_rate < cfg.low_margin_floor
    factor = cfg.low_margin_factor if halved else 1.0
    detail: dict[str, int] = {}
    for line in lines:
        if line.amount < 0:
            raise ValueError("金额不能为负数")
        if line.category not in cfg.rates:
            raise ValueError(f"未知的物料类别：{line.category}")
        value = round(line.amount * cfg.rates[line.category] * factor)
        detail[line.category] = detail.get(line.category, 0) + value
    estimated = sum(detail.values())
    return CommissionResult(
        estimated=estimated,
        confirmed=round(estimated * paid_ratio),
        halved=halved,
        detail=detail,
    )


def check_expense_policy(
    amount: int, headcount: int, expense_type: str = "entertainment", rules: RuleSet | None = None
) -> ExpenseCheck:
    """客户招待按人均标准校验；其他类型暂不限额（TODO：差旅标准）。"""
    if amount < 0:
        raise ValueError("金额不能为负数")
    if headcount <= 0:
        raise ValueError("人数必须大于 0")
    per_person = amount // headcount
    if expense_type != "entertainment":
        return ExpenseCheck(
            per_person=per_person,
            limit_per_person=0,
            over_amount=0,
            need_approval=False,
            reason="该类型暂无限额规则",
        )
    limit = _rules(rules).expense.entertainment_per_person
    over = max(0, amount - limit * headcount)
    need = over > 0
    reason = (
        f"人均 ¥{per_person / 100:.0f} 超出标准 ¥{limit / 100:.0f}/人，超出 ¥{over / 100:.0f}"
        if need
        else f"人均 ¥{per_person / 100:.0f}，在标准 ¥{limit / 100:.0f}/人以内"
    )
    return ExpenseCheck(
        per_person=per_person,
        limit_per_person=limit,
        over_amount=over,
        need_approval=need,
        reason=reason,
    )
