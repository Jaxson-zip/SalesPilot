"""v3 新增的纯函数：阶段默认赢率、停滞判断、报价调价重算、报销人数与参与人文本、任务到期。

全部是纯函数（不读数据库、不取当前时间以外的外部状态），阈值来自 rules.yaml。金额单位：分。
"""

from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel

from app.rules.calculators import _rules, check_margin, discounted_price
from app.rules.loader import RuleSet

LOCAL_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")
FINAL_STAGES = frozenset({"won", "lost"})


# ---------- 商机：阶段默认赢率与停滞 ----------


def default_win_rate(stage: str, rules: RuleSet | None = None) -> int:
    """阶段默认赢率（0–100）。未配置的阶段抛 ValueError。"""
    table = _rules(rules).pipeline.stage_win_rate
    if stage not in table:
        raise ValueError(f"未配置阶段默认赢率：{stage}")
    return table[stage]


def local_date(moment: datetime) -> date:
    """按北京时间取日期；naive 时间视为北京时间。"""
    if moment.tzinfo is None:
        return moment.date()
    return moment.astimezone(LOCAL_TZ).date()


def idle_days_of(last_activity_at: datetime, now: datetime) -> int:
    """距最近一次动态的自然日数（北京时间），不会小于 0。"""
    return max(0, (local_date(now) - local_date(last_activity_at)).days)


def is_stale(stage: str, idle_days: int, rules: RuleSet | None = None) -> bool:
    """未终态且 idle_days ≥ stale_days 视为停滞。"""
    return stage not in FINAL_STAGES and idle_days >= _rules(rules).pipeline.stale_days


# ---------- 报价：调价重算 ----------


class PricedLine(BaseModel):
    qty: int
    unit_cost: int
    unit_price: int
    # 代垫费用：不打折，不算进毛利率（成本 = 单价，不赚钱，算进去会把毛利率拉低）
    passthrough: bool = False


class QuotePricing(BaseModel):
    list_price: int  # 折前合计
    total_cost: int
    total_price: int  # 折后成交价
    discount_rate: float
    margin_rate: float
    margin_passed: bool


def discount_rate_of(list_price: int, total_price: int) -> float:
    """整单折扣率（0–1，4 位小数）；成交价不低于原价时为 0。"""
    if list_price <= 0 or total_price >= list_price:
        return 0.0
    return round((list_price - total_price) / list_price, 4)


def price_quote(
    lines: list[PricedLine], discount_rate: float, rules: RuleSet | None = None
) -> QuotePricing:
    """按明细与整单折扣重算总价和毛利（毛利由 check_margin 计算）。

    代垫费用原价照收：整单折扣只打在其余部分上，毛利率也只按其余部分算。
    """
    if not 0 <= discount_rate < 1:
        raise ValueError("折扣率必须在 [0, 1) 之间")
    if not lines:
        raise ValueError("报价明细不能为空")
    for line in lines:
        if line.qty <= 0 or line.unit_cost < 0 or line.unit_price < 0:
            raise ValueError("数量必须大于 0，单价不能为负数")
    goods = [i for i in lines if not i.passthrough]
    passthrough = sum(i.unit_price * i.qty for i in lines if i.passthrough)
    goods_list = sum(i.unit_price * i.qty for i in goods)
    goods_cost = sum(i.unit_cost * i.qty for i in goods)
    goods_total = discounted_price(goods_list, discount_rate)
    margin = check_margin(goods_cost, goods_total, _rules(rules))
    return QuotePricing(
        list_price=goods_list + passthrough,
        total_cost=goods_cost + passthrough,
        total_price=goods_total + passthrough,
        discount_rate=round(discount_rate, 4),
        margin_rate=margin.margin_rate,
        margin_passed=margin.passed,
    )


def quote_valid_until(created_at: datetime, rules: RuleSet | None = None) -> date:
    """报价有效期：创建日（北京时间）+ quote.valid_days。"""
    return local_date(created_at) + timedelta(days=_rules(rules).quote.valid_days)


# ---------- 报销：参与人 ----------


def headcount_of(contacts: int, colleagues: int, extra_guests: int) -> int:
    """总人数 = 客户方联系人 + 我方同事 + 申请人本人 + 其他人数。"""
    if contacts < 0 or colleagues < 0 or extra_guests < 0:
        raise ValueError("人数不能为负数")
    return contacts + colleagues + 1 + extra_guests


def participants_text(
    contact_names: list[str], self_name: str, colleague_names: list[str], extra_guests: int
) -> str:
    """生成展示用参与人文本：「客户：王律师、陈工；我方：张晨、李薇；其他 2 人」。"""
    parts: list[str] = []
    if contact_names:
        parts.append("客户：" + "、".join(contact_names))
    parts.append("我方：" + "、".join([self_name, *colleague_names]))
    if extra_guests > 0:
        parts.append(f"其他 {extra_guests} 人")
    return "；".join(parts)


# ---------- 任务：今天 / 逾期 ----------


def day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """北京时间「今天」的 [开始, 结束)。"""
    start = datetime.combine(local_date(now), datetime.min.time(), LOCAL_TZ)
    return start, start + timedelta(days=1)


def is_task_overdue(due_at: datetime, done: bool, now: datetime) -> bool:
    """未完成且到期日早于今天（北京时间）即逾期；今天到期的不算逾期。"""
    return not done and local_date(due_at) < local_date(now)


# ---------- 产品目录：近期成交价 ----------


def deal_unit_price(lines: list[tuple[int, int, float]]) -> int | None:
    """按数量加权的成交单价（分）：每行 (明细单价, 数量, 整单折扣率)，单价扣掉整单折扣。"""
    qty = sum(q for _, q, _ in lines)
    if qty <= 0:
        return None
    return round(sum(price * q * (1 - discount) for price, q, discount in lines) / qty)
