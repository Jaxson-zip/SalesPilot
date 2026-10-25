"""行业包：显存估算、GPU 选型、三档配置、毛利回退、注册表。"""

import pytest

from app.common.errors import BizError
from app.packs.base import Configurator, MarginHint
from app.packs.llm_deploy.requirement import LlmDeployRequirement
from app.packs.llm_deploy.vram import estimate_vram, find_model, model_specs, plan_gpus
from app.packs.registry import get_configurator, list_packs

QWEN32 = model_specs()["Qwen3-32B"]


class TestVram:
    def test_qwen32b_fp8_50_concurrency(self) -> None:
        est = estimate_vram(QWEN32, "fp8", concurrency=50, context_tokens=8192)
        assert est.weights_gb == 32.8
        assert est.kv_cache_gb == pytest.approx(53.7, abs=0.1)
        assert est.total_gb == pytest.approx((32.8 + 53.687) * 1.2, abs=0.1)
        assert "kv_cache" in est.formula

    def test_int4_uses_fp8_kv_cache(self) -> None:
        est = estimate_vram(QWEN32, "int4", concurrency=50, context_tokens=8192)
        assert est.weights_gb == 16.4
        assert est.kv_cache_gb == pytest.approx(53.7, abs=0.1)

    def test_bf16_doubles_kv(self) -> None:
        est = estimate_vram(QWEN32, "bf16", concurrency=50, context_tokens=8192)
        assert est.kv_cache_gb == pytest.approx(107.4, abs=0.1)

    def test_invalid_concurrency(self) -> None:
        with pytest.raises(ValueError):
            estimate_vram(QWEN32, "fp8", concurrency=0, context_tokens=8192)

    @pytest.mark.parametrize(
        ("total", "mem", "cards", "nodes"),
        [(10, 48, 1, 1), (84.1, 48, 2, 1), (103.8, 48, 4, 1), (150, 48, 4, 1), (400, 48, 8, 2)],
    )
    def test_plan_gpus(self, total: float, mem: int, cards: int, nodes: int) -> None:
        plan = plan_gpus(total, mem, [1, 2, 4, 8])
        assert (plan.cards_per_node, plan.nodes) == (cards, nodes)
        assert plan.total_mem_gb >= total

    def test_find_model_case_insensitive(self) -> None:
        spec = find_model("给他们出一个 qwen3-32b 私有化方案")
        assert spec is not None and spec.name == "Qwen3-32B"
        assert find_model("没有模型名") is None


class TestLlmDeployConfigurator:
    req = LlmDeployRequirement(model_name="Qwen3-32B", concurrency=50)

    def test_three_tiers_match_prototype(self) -> None:
        tiers = get_configurator("llm_deploy").configure(self.req)
        assert [t.tier for t in tiers] == ["economy", "standard", "premium"]
        economy, standard, premium = tiers
        assert economy.summary.startswith("2× L20")
        assert standard.summary.startswith("4× L20") and standard.recommended
        assert standard.total_price == 37_200_000
        assert premium.summary.startswith("8× H20") and "双机高可用" in premium.summary

    def test_economy_below_floor_then_retry_passes(self) -> None:
        cfg = get_configurator("llm_deploy")
        first = cfg.configure(self.req)
        assert not first[0].margin_ok and first[1].margin_ok and first[2].margin_ok
        retried = cfg.configure(self.req, MarginHint(attempt=1, low_tiers=["economy"]).dump())
        assert all(t.margin_ok for t in retried)
        assert retried[0].total_price > first[0].total_price

    def test_totals_equal_sum_of_items(self) -> None:
        for tier in get_configurator("llm_deploy").configure(self.req):
            cost = sum(i.unit_cost * i.qty for i in tier.items)
            assert tier.total_cost == cost
            listed = sum(i.unit_price * i.qty for i in tier.items)
            assert tier.total_price == round(listed * (1 - tier.discount_rate))

    def test_unknown_model(self) -> None:
        bad = LlmDeployRequirement(model_name="GPT-9", concurrency=10)
        with pytest.raises(ValueError):
            get_configurator("llm_deploy").configure(bad)

    def test_draft_requirement(self) -> None:
        draft = get_configurator("llm_deploy").draft_requirement(
            "给明理律所出 Qwen3-32B 方案，50 人并发，做合同审查，预算 40 万以内"
        )
        assert draft == {
            "model_name": "Qwen3-32B",
            "concurrency": 50,
            "budget": 40_000_000,
            "scene": "合同审查",
        }

    def test_draft_missing_fields(self) -> None:
        assert get_configurator("llm_deploy").draft_requirement("出一个私有化方案") == {}


class TestItOffice:
    def test_configure(self) -> None:
        cfg = get_configurator("it_office")
        req = cfg.requirement_model.model_validate(cfg.draft_requirement("20 名行政，8 名设计"))
        tiers = cfg.configure(req)
        assert len(tiers) == 3
        assert all(t.total_price > 0 for t in tiers)
        assert tiers[1].items[0].qty == 20

    def test_requires_headcount(self) -> None:
        cfg = get_configurator("it_office")
        with pytest.raises(ValueError):
            cfg.requirement_model.model_validate({})


def test_registry_discovers_packs() -> None:
    assert set(list_packs()) >= {"llm_deploy", "it_office"}
    assert isinstance(get_configurator("it_office"), Configurator)


def test_unknown_pack() -> None:
    with pytest.raises(BizError) as exc:
        get_configurator("nope")
    assert exc.value.code == 40401


def test_margin_hint_roundtrip() -> None:
    hint = MarginHint(attempt=2, low_tiers=["economy"])
    assert MarginHint.parse(hint.dump()) == hint
    assert MarginHint.parse("garbage").attempt == 0
    assert MarginHint.parse(None).attempt == 0
