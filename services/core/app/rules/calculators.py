"""纯函数计算器：毛利、折扣、提成、报销制度校验。金额单位一律为整数「分」。"""

from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

from app.rules.loader import HotelRules, RuleSet, load_rules


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
    # 字段名沿用 v1（人均）；unit=night 时表示「每晚」
    per_person: int
    limit_per_person: int
    over_amount: int
    need_approval: bool
    reason: str
    unit: Literal["person", "night"] = "person"
    rule_ref: str = ""


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


def discounted_price(list_price: int, discount_rate: float) -> int:
    """整单折后价（分）。统一口径（前端 lib/money.ts discountedPrice 同样算）：

    折扣率按万分之一取整，折扣额 = 原价 × 折扣率，按分四舍五入（半分进位），折后价 = 原价 − 折扣额。
    全程整数运算：浮点误差和 Python round 的银行家舍入曾让 ¥1.05 打九折在不同界面得到 0.94 / 0.95。
    """
    bp = round(discount_rate * 10_000)
    if list_price <= 0 or bp <= 0:
        return list_price
    return list_price - (list_price * bp + 5_000) // 10_000


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


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def stay_nights(details: Mapping[str, Any] | None) -> int:
    """入住到离店的晚数；日期缺失或不合法时为 0。"""
    d = details or {}
    check_in, check_out = _as_date(d.get("check_in")), _as_date(d.get("check_out"))
    if check_in is None or check_out is None:
        return 0
    return max((check_out - check_in).days, 0)


def _no_limit(amount: int, reason: str) -> ExpenseCheck:
    return ExpenseCheck(
        per_person=amount, limit_per_person=0, over_amount=0, need_approval=False, reason=reason
    )


def _check_hotel(amount: int, details: Mapping[str, Any], hotel: HotelRules | None) -> ExpenseCheck:
    """差旅住宿：每晚标准按城市分档（《费用报销管理制度》3.2），总额超过 标准 × 晚数 需审批。"""
    city = str(details.get("city") or "").strip()
    nights = stay_nights(details)
    if hotel is None or not city or nights < 1:
        return _no_limit(amount, "缺少城市或入住 / 离店日期，无法按住宿标准校验")
    limit = hotel.limit_for(city)
    per_night = amount // nights
    over = max(0, amount - limit * nights)
    head = f"{city} {nights} 晚，每晚 ¥{per_night / 100:.0f}"
    reason = (
        f"{head}，超出标准 ¥{limit / 100:.0f}/晚，超出 ¥{over / 100:.0f}"
        if over
        else f"{head}，在标准 ¥{limit / 100:.0f}/晚以内"
    )
    return ExpenseCheck(
        per_person=per_night,
        limit_per_person=limit,
        over_amount=over,
        need_approval=over > 0,
        reason=reason,
        unit="night",
        rule_ref=hotel.rule_ref,
    )


def check_expense_policy(
    amount: int,
    headcount: int,
    expense_type: str = "entertainment",
    rules: RuleSet | None = None,
    details: Mapping[str, Any] | None = None,
) -> ExpenseCheck:
    """客户招待按人均标准、差旅住宿按每晚标准校验；交通实报实销不限额；
    「其他」类型制度里没有标准，一律交主管审核，不自动通过。"""
    if amount < 0:
        raise ValueError("金额不能为负数")
    if headcount <= 0:
        raise ValueError("人数必须大于 0")
    r = _rules(rules)
    if expense_type == "hotel":
        return _check_hotel(amount, details or {}, r.expense.hotel)
    if expense_type == "transport":
        return _no_limit(amount, "交通费实报实销，不设限额")
    if expense_type != "entertainment":
        return ExpenseCheck(
            per_person=amount,
            limit_per_person=0,
            over_amount=0,
            need_approval=True,
            reason="「其他」类费用报销制度里没有标准，需主管审核",
            rule_ref=r.expense.rule_ref,
        )
    per_person = amount // headcount
    limit = r.expense.entertainment_per_person
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
        rule_ref=r.expense.rule_ref,
    )


def allocate_by_category(
    subtotals: list[tuple[str, int]], total_price: int
) -> list[CommissionLine]:
    """把整单成交价按各类别目录价占比分摊（整单折扣后，提成按实际成交金额计算）。

    分摊结果取整到分，尾差记入最后一个类别，保证合计 = total_price。
    """
    if total_price < 0:
        raise ValueError("金额不能为负数")
    by_cat: dict[str, int] = {}
    for category, amount in subtotals:
        if amount < 0:
            raise ValueError("金额不能为负数")
        by_cat[category] = by_cat.get(category, 0) + amount
    list_total = sum(by_cat.values())
    if list_total == 0:
        return []
    cats = list(by_cat)
    lines: list[CommissionLine] = []
    for cat in cats[:-1]:
        lines.append(
            CommissionLine(category=cat, amount=round(total_price * by_cat[cat] / list_total))
        )
    lines.append(
        CommissionLine(category=cats[-1], amount=total_price - sum(x.amount for x in lines))
    )
    return lines


def paid_ratio_of(paid_amount: int, amount: int) -> float:
    if amount <= 0:
        return 0.0
    return round(min(paid_amount, amount) / amount, 4)


def confirm_commission(estimated: int, paid_amount: int, amount: int) -> int:
    """已确认提成 = 预估提成 × 回款比例，取整到分。"""
    if amount <= 0:
        return 0
    return round(estimated * min(paid_amount, amount) / amount)


def weighted_amount(pairs: list[tuple[int, int]]) -> int:
    """加权金额 = Σ 金额 × 赢率 / 100（赢率为 0–100 的整数），取整到分。"""
    return round(sum(amount * win_rate for amount, win_rate in pairs) / 100)
