"""业务规则与状态机单元测试（不需要数据库）。"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.common import storage
from app.common.auth import Role
from app.common.errors import BizError
from app.crm.models import Opportunity, Quote, QuoteItem
from app.crm.schemas.dashboard import ProductLineUpdate
from app.crm.schemas.finance import PaymentIn
from app.crm.schemas.opportunity import StageChange
from app.crm.services import (
    approval_service,
    attachment_service,
    opportunity_service,
    pack_service,
    payment_service,
    quote_service,
)
from app.crm.services.codes import format_code, month_start, parse_seq
from app.crm.services.demo import DEMO_USERS
from app.crm.services.expense_service import policy_check
from app.packs.base import BomItem, SolutionTier, adjust_tier, price_tier
from app.rules import (
    allocate_by_category,
    confirm_commission,
    load_rules,
    paid_ratio_of,
    weighted_amount,
)

SALES, MANAGER, ADMIN = (DEMO_USERS[r] for r in (Role.SALES, Role.MANAGER, Role.ADMIN))
RULES = load_rules()


class FakeSession:
    """只记录 add / flush，用于不落库地测试状态机。"""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def scalars(self, _stmt: Any) -> Any:  # 输单收尾查报价 / 待办：不落库时没有数据
        return type("Rows", (), {"all": lambda self: []})()


# ---------- 规则计算 ----------


class TestCommissionAllocation:
    def test_proportional_and_sum_preserved(self) -> None:
        lines = allocate_by_category([("hardware", 200), ("service", 100)], 270)
        assert [(x.category, x.amount) for x in lines] == [("hardware", 180), ("service", 90)]

    def test_remainder_goes_to_last(self) -> None:
        lines = allocate_by_category([("hardware", 1), ("software", 1), ("service", 1)], 100)
        assert sum(x.amount for x in lines) == 100 and lines[-1].amount == 34

    def test_merges_same_category_and_empty(self) -> None:
        lines = allocate_by_category([("hardware", 50), ("hardware", 50)], 100)
        assert [(x.category, x.amount) for x in lines] == [("hardware", 100)]
        assert allocate_by_category([], 100) == []
        assert allocate_by_category([("hardware", 0)], 100) == []

    def test_negative(self) -> None:
        with pytest.raises(ValueError):
            allocate_by_category([("hardware", -1)], 1)
        with pytest.raises(ValueError):
            allocate_by_category([("hardware", 1)], -1)


@pytest.mark.parametrize(
    ("estimated", "paid", "amount", "expected"),
    [(700_000, 0, 15_000_000, 0), (700_000, 6_000_000, 15_000_000, 280_000),
     (700_000, 15_000_000, 15_000_000, 700_000), (101, 1, 2, 50), (100, 5, 0, 0),
     (100, 20, 10, 100)],
)  # fmt: skip
def test_confirm_commission(estimated: int, paid: int, amount: int, expected: int) -> None:
    assert confirm_commission(estimated, paid, amount) == expected


def test_paid_ratio_and_weighted() -> None:
    assert paid_ratio_of(32_400_000, 81_000_000) == 0.4
    assert paid_ratio_of(1, 0) == 0.0 and paid_ratio_of(20, 10) == 1.0
    assert weighted_amount([(1000, 50), (300, 10)]) == 530
    assert weighted_amount([]) == 0


class TestExpensePolicy:
    def test_boundary_exactly_at_limit_passes(self) -> None:
        assert policy_check("entertainment", 60_000, 4, RULES).passed

    def test_over_limit(self) -> None:
        c = policy_check("entertainment", 60_001, 4, RULES)
        assert not c.passed and c.over_amount == 1 and c.rule_ref

    def test_other_type_has_no_limit(self) -> None:
        c = policy_check("transport", 999_999, 1, RULES)
        assert c.passed and c.limit_per_person == 0 and c.rule_ref == ""

    def test_required_kinds(self) -> None:
        assert RULES.expense.kinds_for("entertainment") == ["invoice", "receipt"]
        assert RULES.expense.kinds_for("hotel") == ["invoice"]


# ---------- 单号 / 文件 ----------


def test_codes() -> None:
    assert format_code("C", 2026, 7) == "C-2026-007"
    assert parse_seq("Q-2026-019", "Q", 2026) == 19
    assert parse_seq("Q-2025-019", "Q", 2026) == 0 and parse_seq("Q-2026-x", "Q", 2026) == 0
    assert parse_seq(None, "Q", 2026) == 0
    start = month_start(datetime(2026, 10, 31, 20, 0, tzinfo=UTC))  # 北京时间已是 11 月 1 日
    assert (start.month, start.day, start.hour) == (11, 1, 0)


class TestFiles:
    def test_detect_mime(self) -> None:
        assert storage.detect_mime(b"%PDF-1.4") == "application/pdf"
        assert storage.detect_mime(b"\x89PNG\r\n\x1a\n...") == "image/png"
        assert storage.detect_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
        assert storage.detect_mime(b"MZ") is None

    def test_name_matches(self) -> None:
        assert storage.name_matches("a.JPEG", "image/jpeg")
        assert not storage.name_matches("a.exe", "application/pdf")

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(ValueError):
            storage.path_of("../../etc/passwd")

    def test_validate_file(self) -> None:
        allowed = RULES.attachment.allowed_types
        assert (
            attachment_service.validate_file("a.pdf", b"%PDF-1.4", 100, allowed)
            == "application/pdf"
        )
        cases = [
            ("a.pdf", b"", 100),
            ("a.pdf", b"%PDF-" + b"0" * 200, 100),
            ("a.png", b"%PDF-1.4", 100),
            ("a.exe", b"MZ", 100),
        ]
        for name, content, size in cases:
            with pytest.raises(BizError) as exc:
                attachment_service.validate_file(name, content, size, allowed)
            assert exc.value.code == 40001


# ---------- 商机阶段状态机 ----------


def _opp(stage: str) -> Opportunity:
    return Opportunity(id=uuid.uuid4(), stage=stage, owner_id=SALES.id, team_id=SALES.team_id)


class TestOpportunityStage:
    def test_lost_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            StageChange(stage="lost")
        with pytest.raises(ValidationError):
            StageChange(stage="lost", lost_reason="  ")
        assert StageChange(stage="won").lost_reason is None

    @pytest.mark.parametrize("final", ["won", "lost"])
    def test_final_cannot_change(self, final: str) -> None:
        with pytest.raises(BizError) as exc:
            opportunity_service.apply_stage(
                FakeSession(), SALES, _opp(final), StageChange(stage="lead")
            )  # type: ignore[arg-type]
        assert exc.value.code == 42201 and exc.value.data["rule"] == "opportunity_stage_final"

    def test_change_writes_activity(self) -> None:
        db, opp = FakeSession(), _opp("qualified")
        opportunity_service.apply_stage(db, SALES, opp, StageChange(stage="proposal"))  # type: ignore[arg-type]
        assert opp.stage == "proposal" and opp.closed_at is None
        assert (
            db.added[0].action == "stage_changed" and db.added[0].content == "需求确认 → 方案报价"
        )

    def test_lost_sets_reason_and_closed_at(self) -> None:
        db, opp = FakeSession(), _opp("negotiation")
        change = StageChange(stage="lost", lost_reason="预算取消")
        opportunity_service.apply_stage(db, MANAGER, opp, change, "agent")  # type: ignore[arg-type]
        assert opp.lost_reason == "预算取消" and opp.closed_at is not None
        assert (
            db.added[0].actor_id is None and db.added[0].owner_id == SALES.id
        )  # 动态归属商机负责人

    def test_same_stage_is_noop(self) -> None:
        db = FakeSession()
        opportunity_service.apply_stage(db, SALES, _opp("lead"), StageChange(stage="lead"))  # type: ignore[arg-type]
        assert db.added == []


# ---------- 报价状态机 ----------

LEGAL = {("draft", "submit"), ("approved", "send"), ("sent", "accept"), ("sent", "reject")}
STATUSES = ["draft", "pending_approval", "approved", "sent", "accepted", "rejected"]


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("action", ["submit", "send", "accept", "reject"])
def test_quote_transition_matrix(status: str, action: str) -> None:
    quote = Quote(status=status)
    if (status, action) in LEGAL:
        quote_service._check_transition(quote, action)
        return
    with pytest.raises(BizError) as exc:
        quote_service._check_transition(quote, action)
    assert exc.value.code == 42201 and exc.value.data["rule"] == "quote_status_transition"


def _quote(cost: int, price: int, list_price: int) -> tuple[Quote, list[QuoteItem]]:
    item = QuoteItem(sku="X", name="X", unit="台", qty=1, unit_cost=cost, unit_price=list_price,
                     category="hardware")  # fmt: skip
    return Quote(total_cost=cost, total_price=price), [item]


class TestQuoteApprovalRules:
    def test_margin_at_floor_passes(self) -> None:
        quote, items = _quote(75, 100, 100)
        assert quote_service.approval_reasons(quote, items, RULES) == []

    def test_low_margin(self) -> None:
        quote, items = _quote(772, 1000, 1000)
        assert quote_service.approval_reasons(quote, items, RULES) == [
            "毛利 22.8% < 25%，需要主管审批或调整配置"
        ]

    def test_discount_boundary(self) -> None:
        quote, items = _quote(10, 90, 100)  # 折扣恰好 10%
        assert quote_service.approval_reasons(quote, items, RULES) == []
        quote, items = _quote(10, 89, 100)
        assert quote_service.approval_reasons(quote, items, RULES)[0].startswith("折扣 11.0%")


# ---------- 角色权限 ----------


def test_role_checks() -> None:
    for user in (SALES, ADMIN):
        with pytest.raises(BizError) as exc:
            approval_service.require_manager(user)
        assert exc.value.code == 40301
    approval_service.require_manager(MANAGER)
    with pytest.raises(BizError) as exc:
        payment_service.add_payment(FakeSession(), SALES, uuid.uuid4(), PaymentIn(amount=1))  # type: ignore[arg-type]
    assert exc.value.code == 40301
    with pytest.raises(BizError) as exc:
        pack_service.update_product_line(FakeSession(), MANAGER, uuid.uuid4(), ProductLineUpdate())  # type: ignore[arg-type]
    assert exc.value.code == 40301


def test_approval_target_status() -> None:
    assert approval_service.TARGET_STATUS[("quote", "reject")] == "draft"
    assert approval_service.TARGET_STATUS[("expense", "reject")] == "rejected"
    assert approval_service.TARGET_STATUS[("quote", "approve")] == "approved"


class TestAdjustTier:
    """方案卡上调整数量后重算：单价和折扣不变，毛利由规则重算，成本构成去掉。"""

    def _tier(self) -> SolutionTier:
        items = [
            BomItem(
                sku="A",
                name="服务器",
                category="hardware",
                unit="台",
                qty=2,
                unit_cost=70,
                unit_price=100,
            ),
            BomItem(
                sku="B",
                name="监控",
                category="service",
                unit="项",
                qty=1,
                unit_cost=10,
                unit_price=40,
            ),
        ]
        tier = SolutionTier(
            tier="standard",
            name="标准版",
            summary="",
            items=items,
            discount_rate=0.1,
            specs={"cost_breakdown": {"labor": 1}, "gpu": "L20"},
        )
        return price_tier(tier, load_rules())

    def test_remove_and_change_qty(self) -> None:
        out = adjust_tier(self._tier(), {"A": 3, "B": 0}, load_rules())
        assert [(i.sku, i.qty) for i in out.items] == [("A", 3)]
        assert (out.total_cost, out.total_price) == (210, 270)
        assert out.margin_rate == round((270 - 210) / 270, 4)
        assert out.specs == {"gpu": "L20", "adjusted": True}
        assert out.summary == "已调整：去掉 监控；改了 1 项数量"

    def test_summary_recounts_person_days(self) -> None:
        """回归（审查 SP-003）：调整后摘要仍是原来的「约 N 人天」，与物料对不上。"""
        days = [
            BomItem(
                sku=s, name=n, category="service", unit="人天", qty=q, unit_cost=1, unit_price=2
            )
            for s, n, q in [("M1", "订单管理", 7), ("M2", "测试", 3)]
        ]
        tier = SolutionTier(
            tier="economy", name="经济版", summary="2 个模块 · 约 10 人天", items=days
        )
        out = adjust_tier(tier, {"M1": 8}, load_rules())
        assert out.summary == "已调整：人天合计 11 人天（原方案约 10 人天）；改了 1 项数量"
        out = adjust_tier(tier, {"M1": 0}, load_rules())
        assert out.summary == "已调整：人天合计 3 人天（原方案约 10 人天）；去掉 订单管理"
        assert adjust_tier(tier, {"M1": 7}, load_rules()).summary == tier.summary

    @pytest.mark.parametrize("qty", [{"X": 1}, {"A": -1}, {"A": 10_000}, {"A": 0, "B": 0}])
    def test_invalid(self, qty: dict[str, int]) -> None:
        with pytest.raises(ValueError):
            adjust_tier(self._tier(), qty, load_rules())


@pytest.mark.parametrize(
    ("list_price", "rate", "expected"),
    [
        (105, 0.1, 94),  # 回归：折扣额 10.5 分半分进位，折后 94（方案预览曾算成 95）
        (115, 0.1, 103),
        (114, 0.1, 103),
        (100_000, 0.05, 95_000),
        (999, 0.0333, 966),
        (500, 0, 500),
        (1_000_000_000_000, 0.1234, 876_600_000_000),
        (999_999_999_999, 0.0001, 999_899_999_999),
    ],
)
def test_discounted_price_matches_web(list_price: int, rate: float, expected: int) -> None:
    """和前端 lib/__tests__/money.test.ts 同一组用例：各个界面和后端的舍入必须一致。"""
    from app.rules import discounted_price

    assert discounted_price(list_price, rate) == expected
