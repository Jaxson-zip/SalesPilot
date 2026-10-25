"""规则计算器：正常、边界、异常三类情况。"""

import pytest

from app.packs.registry import get_pack
from app.rules import (
    CommissionLine,
    calc_commission,
    check_discount,
    check_expense_policy,
    check_margin,
    load_rules,
)


class TestMargin:
    def test_pass(self) -> None:
        r = check_margin(26_250_000, 37_200_000)
        assert r.passed and r.margin_rate == pytest.approx(0.2944, abs=1e-4)

    def test_fail_below_floor(self) -> None:
        r = check_margin(14_100_000, 18_032_000)
        assert not r.passed
        assert "21.8%" in r.reason and "25%" in r.reason

    def test_exactly_floor_passes(self) -> None:
        assert check_margin(75, 100).passed

    def test_zero_price_fails(self) -> None:
        r = check_margin(0, 0)
        assert not r.passed and r.margin_rate == 0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            check_margin(-1, 100)

    def test_threshold_from_yaml(self) -> None:
        assert load_rules().margin.floor_rate == 0.25


class TestDiscount:
    def test_within_limit(self) -> None:
        assert check_discount(100_000, 90_000)

    def test_over_limit(self) -> None:
        assert not check_discount(100_000, 88_000)

    def test_invalid_list_price(self) -> None:
        with pytest.raises(ValueError):
            check_discount(0, 0)


class TestCommission:
    lines = [  # noqa: RUF012
        CommissionLine(category="hardware", amount=26_200_000),
        CommissionLine(category="service", amount=11_000_000),
    ]

    def test_normal(self) -> None:
        r = calc_commission(self.lines, margin_rate=0.30)
        assert r.detail == {"hardware": 786_000, "service": 880_000}
        assert r.estimated == 1_666_000 and r.confirmed == 1_666_000 and not r.halved

    def test_low_margin_halved(self) -> None:
        r = calc_commission(self.lines, margin_rate=0.20)
        assert r.halved and r.estimated == 833_000

    def test_paid_ratio(self) -> None:
        r = calc_commission(self.lines, margin_rate=0.30, paid_ratio=0.5)
        assert r.confirmed == 833_000

    def test_empty_lines(self) -> None:
        assert calc_commission([], 0.3).estimated == 0

    def test_invalid_ratio(self) -> None:
        with pytest.raises(ValueError):
            calc_commission(self.lines, 0.3, paid_ratio=1.5)

    def test_unknown_category(self) -> None:
        with pytest.raises(ValueError):
            calc_commission([CommissionLine(category="gift", amount=1)], 0.3)


class TestExpense:
    def test_over_standard(self) -> None:
        r = check_expense_policy(86_000, 4)
        assert r.need_approval and r.per_person == 21_500 and r.over_amount == 26_000

    def test_within_standard(self) -> None:
        r = check_expense_policy(42_000, 3)
        assert not r.need_approval and r.over_amount == 0

    def test_exact_standard(self) -> None:
        assert not check_expense_policy(60_000, 4).need_approval

    def test_other_type_no_limit(self) -> None:
        assert not check_expense_policy(58_000, 1, "hotel").need_approval

    @pytest.mark.parametrize(("amount", "headcount"), [(-1, 1), (100, 0)])
    def test_invalid(self, amount: int, headcount: int) -> None:
        with pytest.raises(ValueError):
            check_expense_policy(amount, headcount)


def test_pack_rules_override() -> None:
    rules = load_rules(get_pack("llm_deploy").rules_file)
    assert rules.margin.floor_rate == 0.25
    assert rules.commission.rates["hardware"] == 0.03
