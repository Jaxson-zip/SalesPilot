"""软件外包行业包：规则兜底的需求识别、模块人天、多端系数、三档差异、工期与预算推荐。"""

from app.packs.base import Configurator
from app.packs.registry import get_configurator, list_packs
from app.packs.software_outsourcing.configurator import SoftwareOutsourcingConfigurator
from app.packs.software_outsourcing.requirement import SoftwareRequirement
from app.rules import check_margin

TEXT = (
    "做个连锁门店预约小程序，要会员登录、在线预约和微信支付，"
    "还要管理后台看报表，2个月上线，预算15万"
)


def cfg() -> SoftwareOutsourcingConfigurator:
    c = get_configurator("software_outsourcing")
    assert isinstance(c, SoftwareOutsourcingConfigurator)
    return c


def req(**kw: object) -> SoftwareRequirement:
    base: dict[str, object] = {
        "platforms": ["mini_program", "admin"],
        "modules": [
            {"key": "account", "name": "会员登录", "complexity": "simple"},
            {"key": "booking", "name": "在线预约", "complexity": "complex"},
            {"key": "report", "name": "数据报表", "must": False},
        ],
    }
    return SoftwareRequirement.model_validate({**base, **kw})


def test_registered() -> None:
    assert "software_outsourcing" in list_packs()
    assert isinstance(cfg(), Configurator)


def test_rule_draft_without_llm() -> None:
    d = cfg().draft_requirement(TEXT)
    assert d["platforms"] == ["mini_program", "admin"]
    assert [m["key"] for m in d["modules"]] == ["account", "booking", "payment", "report"]
    assert d["deadline_weeks"] == 8 and d["budget"] == 15_000_000


def test_lines_and_totals() -> None:
    tiers = cfg().configure(req())
    std = next(t for t in tiers if t.tier == "standard")
    by = {i.sku: i for i in std.items}
    assert by["MOD-ACCOUNT"].qty == 3 and by["MOD-BOOKING"].qty == 12 and by["MOD-REPORT"].qty == 6
    dev = 5 + 4 + 3 + 12 + 6  # 架构 + 后台 + 模块
    assert by["SVC-QA"].qty == round(dev * 0.2) and by["SVC-ANALYSIS"].qty == round(dev * 0.1)
    assert std.total_price == sum(i.total_price for i in std.items)
    assert std.recommended and std.specs["person_days"] == sum(
        i.qty for i in std.items if i.unit == "人天"
    )
    assert all(check_margin(t.total_cost, t.total_price, cfg().rules).passed for t in tiers)


def test_tiers_differ() -> None:
    eco, std, pre = cfg().configure(req(platforms=["mini_program", "app", "admin"]))
    skus = {i.sku for i in eco.items}
    assert "MOD-REPORT" not in skus  # 经济版只做首期必须的
    assert eco.specs["platforms"] == ["mini_program", "admin"]  # 只做第一个客户端
    booking = {t.tier: next(i.qty for i in t.items if i.sku == "MOD-BOOKING") for t in (eco, std)}
    assert booking == {"economy": 12, "standard": 18}  # 两个客户端 × 1.5
    assert {"SVC-OPS", "SVC-HANDOVER"} <= {i.sku for i in pre.items}
    assert eco.total_price < std.total_price < pre.total_price


def test_custom_and_duplicate_modules() -> None:
    r = req(
        modules=[
            {"key": "payment", "name": "支付"},
            {"key": "payment", "name": "微信支付"},
            {"key": "custom", "name": "对接门店收银机", "complexity": "complex"},
            {"key": "whatever", "name": "模型自造的 key"},
        ]
    )
    std = cfg().configure(r)[1]
    mods = [i for i in std.items if i.sku.startswith("MOD-")]
    assert [i.sku for i in mods] == ["MOD-PAYMENT", "MOD-CUSTOM-2", "MOD-WHATEVER"]
    assert mods[1].qty == 10 and mods[2].qty == 6  # 未知 key 按定制功能中等估


def test_deadline_and_budget() -> None:
    tiers = cfg().configure(req(deadline_weeks=1))
    assert "比期望工期多" in tiers[1].summary
    eco, std, _ = cfg().configure(req())
    budget = (eco.total_price + std.total_price) // 2
    picked = [t.tier for t in cfg().configure(req(budget=budget)) if t.recommended]
    assert picked == ["economy"]
    # 预算连经济版都不够：仍推荐经济版，并提示砍功能或分期
    low = cfg().configure(req(budget=eco.total_price // 2))
    assert low[0].recommended and "建议砍掉部分功能或分期" in low[0].summary
    assert "建议砍掉" not in cfg().configure(req(budget=budget))[0].summary


def test_extract_hint_lists_library() -> None:
    hint = cfg().extract_hint()
    assert "booking=在线预约排期" in hint and "custom" in hint and "不要估算人天" in hint


def test_solo_fullstack_pricing() -> None:
    """个人全栈：全栈单价、研发人天 × 提效系数、不计项目管理，工期按 1 人算。"""
    team = {t.tier: t for t in cfg().configure(req())}["standard"]
    solo = {t.tier: t for t in cfg().configure(req(team_size=1))}["standard"]
    skus = {i.sku for i in solo.items}
    assert "SVC-PM" not in skus and "SVC-PM" in {i.sku for i in team.items}
    assert {i.unit_price for i in solo.items if i.unit == "人天"} == {150_000}
    assert solo.specs["delivery"] == "solo" and solo.specs["team_size"] == 1
    assert solo.specs["person_days"] < team.specs["person_days"]
    assert solo.specs["weeks"] > team.specs["weeks"]
    assert "个人全栈" in solo.summary


def test_solo_words_and_cost_breakdown() -> None:
    assert cfg().draft_requirement("我一个人全栈做，" + TEXT)["team_size"] == 1
    tier = {t.tier: t for t in cfg().configure(req())}["standard"]
    cb = tier.specs["cost_breakdown"]
    days = sum(i.qty for i in tier.items if i.unit == "人天")
    assert cb["ai_tools"] == days * 3000
    assert sum(cb.values()) == sum(i.total_cost for i in tier.items)
    # 第三方费用按成本代采，小程序要认证费
    tp = [i for i in tier.items if i.sku.startswith("TP-")]
    assert {i.sku for i in tp} == {"TP-CLOUD-1Y", "TP-DOMAIN-SSL", "TP-MP-CERT"}
    assert all(i.unit_cost == i.unit_price for i in tp)
    assert cb["third_party"] == sum(i.total_cost for i in tp)


def test_ai_feature_monthly_cost() -> None:
    """交付的软件带 AI 功能：估算上线后每月的大模型调用费，不计入报价。"""
    plain = {t.tier: t for t in cfg().configure(req())}["standard"]
    assert plain.specs["ai_monthly_cost"] == 0
    mods = [{"key": "ai", "name": "智能客服", "complexity": "medium"}]
    tier = {t.tier: t for t in cfg().configure(req(modules=mods))}["standard"]
    assert tier.specs["ai_monthly_cost"] > 0
    assert "AI 调用费" in tier.summary
    assert tier.total_price == sum(i.total_price for i in tier.items)


def test_clarify_range_and_questions() -> None:
    mods = [
        {"key": "account", "name": "会员登录"},
        {"key": "booking", "name": "在线预约", "complexity": "complex"},
        {"key": "rbac", "name": "多门店权限", "source": "inferred"},
    ]
    info = cfg().clarify(req(modules=mods))
    assert info["inferred"] == 1
    assert info["price_low"] < info["price_high"]
    assert "多门店权限" in info["questions"][0] and len(info["questions"]) <= 5
    asked = cfg().clarify(req(modules=mods, questions=["教练和学员是两套界面吗？"]))
    assert asked["questions"] == ["教练和学员是两套界面吗？"]


def test_extract_hint_includes_current_draft() -> None:
    plain = cfg().extract_hint()
    draft = {"platforms": ["app"], "modules": [{"key": "map", "name": "门店地图"}]}
    with_draft = cfg().extract_hint(draft)
    assert "门店地图" in with_draft and "门店地图" not in plain
