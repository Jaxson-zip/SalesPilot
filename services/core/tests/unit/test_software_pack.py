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


def test_extract_hint_lists_library() -> None:
    hint = cfg().extract_hint()
    assert "booking=在线预约排期" in hint and "custom" in hint and "不要估算人天" in hint
