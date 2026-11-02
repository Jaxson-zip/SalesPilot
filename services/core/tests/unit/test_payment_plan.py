"""回款计划：拆期、按顺序分摊实收、逾期判断（B9）。"""

from datetime import date

from app.crm.services.payment_plan import PlanInput, allocate, default_plan, next_due, split_amount
from app.rules.loader import load_rules

SIGNED = date(2026, 9, 1)


def test_split_keeps_total_and_puts_rounding_on_last() -> None:
    assert split_amount(100_001, [0.3, 0.6, 0.1]) == [30_000, 60_001, 10_000]
    assert sum(split_amount(81_000_000, [0.3, 0.6, 0.1])) == 81_000_000


def test_default_plan_follows_rules_yaml() -> None:
    plan = default_plan(1_000_000, SIGNED, load_rules().payment.schedule)
    assert [(p.name, p.amount) for p in plan] == [
        ("预付款", 300_000),
        ("到货验收款", 600_000),
        ("质保金", 100_000),
    ]
    assert plan[0].due_date == SIGNED and plan[1].due_date == date(2026, 10, 31)


def test_allocate_fifo_and_overdue() -> None:
    plans = [
        PlanInput("预付款", 300, date(2026, 9, 1)),
        PlanInput("到货验收款", 600, date(2026, 10, 1)),
        PlanInput("质保金", 100, date(2027, 9, 1)),
    ]
    states = allocate(plans, 400, today=date(2026, 10, 11))
    assert [(s.paid, s.status, s.overdue_days) for s in states] == [
        (300, "paid", 0),
        (100, "overdue", 10),  # 到期 10 天还差 500
        (0, "pending", 0),
    ]
    assert next_due(states) == states[1]
    before_due = allocate(plans, 400, today=date(2026, 9, 20))
    assert before_due[1].status == "partial"
    assert next_due(allocate(plans, 1000, today=date(2026, 10, 11))) is None
