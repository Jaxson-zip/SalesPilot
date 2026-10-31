"""v3 纯函数：阶段默认赢率、停滞判断、报价调价重算、报销人数与参与人文本、任务到期。"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.rules import load_rules
from app.rules.crm_calc import (
    LOCAL_TZ,
    PricedLine,
    day_bounds,
    default_win_rate,
    discount_rate_of,
    headcount_of,
    idle_days_of,
    is_stale,
    is_task_overdue,
    participants_text,
    price_quote,
    quote_valid_until,
)

NOW = datetime(2026, 10, 26, 10, 0, tzinfo=LOCAL_TZ)


class TestWinRate:
    @pytest.mark.parametrize(
        ("stage", "rate"),
        [("lead", 10), ("qualified", 25), ("proposal", 50), ("negotiation", 75), ("won", 100),
         ("lost", 0)],
    )  # fmt: skip
    def test_defaults_from_rules_yaml(self, stage: str, rate: int) -> None:
        assert default_win_rate(stage) == rate

    def test_unknown_stage(self) -> None:
        with pytest.raises(ValueError):
            default_win_rate("unknown")

    def test_rules_override(self) -> None:
        rules = load_rules()
        custom = rules.model_copy(
            update={"pipeline": rules.pipeline.model_copy(update={"stage_win_rate": {"lead": 5}})}
        )
        assert default_win_rate("lead", custom) == 5


class TestStale:
    def test_idle_days_by_local_date(self) -> None:
        # UTC 10-25 17:00 = 北京 10-26 01:00，同一天
        assert idle_days_of(datetime(2026, 10, 25, 17, 0, tzinfo=UTC), NOW) == 0
        assert idle_days_of(NOW - timedelta(days=14), NOW) == 14
        assert idle_days_of(NOW + timedelta(days=1), NOW) == 0  # 未来时间不为负

    @pytest.mark.parametrize(("idle", "stale"), [(13, False), (14, True), (15, True)])
    def test_boundary(self, idle: int, stale: bool) -> None:
        assert load_rules().pipeline.stale_days == 14
        assert is_stale("proposal", idle) is stale

    @pytest.mark.parametrize("stage", ["won", "lost"])
    def test_final_stage_never_stale(self, stage: str) -> None:
        assert not is_stale(stage, 100)


class TestQuotePricing:
    LINES = [  # noqa: RUF012
        PricedLine(qty=1, unit_cost=7_000_000, unit_price=10_000_000),
        PricedLine(qty=2, unit_cost=1_000_000, unit_price=2_500_000),
    ]

    def test_no_discount(self) -> None:
        p = price_quote(self.LINES, 0)
        assert (p.list_price, p.total_cost, p.total_price) == (15_000_000, 9_000_000, 15_000_000)
        assert p.margin_rate == 0.4 and p.margin_passed and p.discount_rate == 0

    def test_discount_recomputes_margin(self) -> None:
        p = price_quote(self.LINES, 0.2)
        assert p.total_price == 12_000_000 and p.margin_rate == 0.25 and p.margin_passed
        low = price_quote(self.LINES, 0.3)
        assert low.total_price == 10_500_000 and low.margin_rate == 0.1429 and not low.margin_passed

    def test_passthrough_not_discounted_nor_in_margin(self) -> None:
        """代垫费用 2 万（成本 = 单价）：原价照收，不打折，不拉低毛利率。"""
        trip = PricedLine(qty=1, unit_cost=2_000_000, unit_price=2_000_000, passthrough=True)
        p = price_quote([*self.LINES, trip], 0.2)
        assert p.total_price == 12_000_000 + 2_000_000
        assert p.total_cost == 9_000_000 + 2_000_000 and p.list_price == 17_000_000
        assert p.margin_rate == 0.25 and p.margin_passed  # 和没有代垫费用时一样

    def test_rounding_to_fen(self) -> None:
        p = price_quote([PricedLine(qty=1, unit_cost=0, unit_price=333)], 0.1)
        assert p.total_price == 300  # 299.7 → 300

    @pytest.mark.parametrize("rate", [-0.1, 1, 1.5])
    def test_invalid_discount(self, rate: float) -> None:
        with pytest.raises(ValueError):
            price_quote(self.LINES, rate)

    def test_invalid_lines(self) -> None:
        with pytest.raises(ValueError):
            price_quote([], 0)
        with pytest.raises(ValueError):
            price_quote([PricedLine(qty=0, unit_cost=1, unit_price=1)], 0)

    def test_discount_rate_of(self) -> None:
        assert discount_rate_of(10_000, 9_000) == 0.1
        assert discount_rate_of(10_000, 10_000) == 0
        assert discount_rate_of(10_000, 12_000) == 0
        assert discount_rate_of(0, 0) == 0

    def test_valid_until(self) -> None:
        created = datetime(2026, 10, 25, 20, 0, tzinfo=UTC)  # 北京 10-26 04:00
        assert quote_valid_until(created) == date(2026, 11, 25)


class TestParticipants:
    def test_headcount(self) -> None:
        assert headcount_of(2, 1, 0) == 4
        assert headcount_of(0, 0, 0) == 1
        assert headcount_of(1, 0, 3) == 5
        with pytest.raises(ValueError):
            headcount_of(-1, 0, 0)

    def test_text(self) -> None:
        assert (
            participants_text(["王律师", "陈工"], "张晨", ["李薇"], 0)
            == "客户：王律师、陈工；我方：张晨、李薇"
        )
        assert participants_text([], "张晨", [], 2) == "我方：张晨；其他 2 人"


class TestTaskDue:
    def test_day_bounds_local(self) -> None:
        start, end = day_bounds(NOW)
        assert start == datetime(2026, 10, 26, tzinfo=LOCAL_TZ)
        assert end - start == timedelta(days=1)

    def test_overdue_is_date_based(self) -> None:
        assert not is_task_overdue(NOW - timedelta(hours=2), False, NOW)  # 今天早些时候：今天到期
        assert is_task_overdue(NOW - timedelta(days=1), False, NOW)
        assert not is_task_overdue(NOW - timedelta(days=1), True, NOW)  # 已完成不算逾期
