"""软件外包行业包：规则兜底的需求识别、模块人天、多端系数、三档差异、工期与预算推荐。"""

import pytest

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
    # 预算怎么收缩都放不下：经济版保持原样，提示砍功能或分期
    low = cfg().configure(req(budget=100))
    assert low[0].recommended and "建议砍掉部分功能或分期" in low[0].summary
    assert low[0].total_price == eco.total_price
    assert "建议砍掉" not in cfg().configure(req(budget=budget))[0].summary


def test_budget_simplifies_economy() -> None:
    """预算略低于经济版：功能改做基础版，价格放进预算，标准版、高配版不变。"""
    eco, std, pre = cfg().configure(req())
    tiers = cfg().configure(req(budget=eco.total_price - 1))
    fit = tiers[0]
    assert fit.recommended and fit.total_price < eco.total_price
    assert "按客户预算" in fit.summary and "二期再做" not in fit.summary
    assert {m["complexity"] for m in fit.specs["modules"]} == {"simple"}
    assert fit.margin_ok  # 只减范围、不压单价，毛利照常
    assert (tiers[1].total_price, tiers[2].total_price) == (std.total_price, pre.total_price)


def test_budget_defers_modules_to_phase_two() -> None:
    """基础版还放不下：把排在后面的模块挪到二期，AI 推断的先挪。"""
    only_login = req(modules=[{"key": "account", "name": "会员登录", "complexity": "simple"}])
    budget = cfg().configure(only_login)[0].total_price
    fit = cfg().configure(req(budget=budget))[0]
    assert fit.total_price <= budget
    assert [m["name"] for m in fit.specs["modules"]] == ["会员登录"]
    assert "二期再做：在线预约" in fit.summary
    mods = [
        {"key": "booking", "name": "在线预约", "source": "mentioned"},
        {"key": "account", "name": "会员登录", "source": "inferred"},
    ]
    only_booking = req(modules=[{"key": "booking", "name": "在线预约", "complexity": "simple"}])
    budget = cfg().configure(only_booking)[0].total_price
    inferred_first = cfg().configure(req(modules=mods, budget=budget))[0]
    assert [m["name"] for m in inferred_first.specs["modules"]] == ["在线预约"]


def test_extract_hint_lists_library() -> None:
    hint = cfg().extract_hint()
    assert "booking=在线预约排期" in hint and "custom" in hint and "不要估算人天" in hint


def test_solo_fullstack_pricing() -> None:
    """个人全栈：全栈单价、研发人天 × 提效系数、不计项目管理，工期按 1 人算。"""
    team = {t.tier: t for t in cfg().configure(req())}["standard"]
    solo = {t.tier: t for t in cfg().configure(req(team_size=1))}["standard"]
    skus = {i.sku for i in solo.items}
    assert "SVC-PM" not in skus and "SVC-PM" in {i.sku for i in team.items}
    assert {i.unit_price for i in solo.items if i.unit == "人天"} == {40_000}
    # 部署、运维、交付用个人价；架构不打 AI 提效折扣
    assert {i.sku for i in solo.items if i.unit != "人天"} == {"SVC-DEPLOY-SOLO", "SVC-OPS-SOLO"}
    arch = next(i for i in solo.items if i.sku == "SVC-ARCH")
    assert arch.qty == cfg().params["base_days"]
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
    # 默认第三方费用由客户自付：不在报价里，单列在 client_costs（小程序要认证费）
    assert not [i for i in tier.items if i.sku.startswith("TP-")]
    assert cb["third_party"] == 0
    yearly = {c["name"]: c for c in tier.specs["client_costs"] if c["period"] == "year"}
    assert set(yearly) == {"云服务器与数据库", "域名与 SSL 证书", "微信小程序认证费"}
    assert yearly["微信小程序认证费"]["note"] == "以客户主体开通"
    assert "由客户自付" in tier.summary


def test_third_party_in_quote_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """管理员打开「第三方费用计入报价」：按成本代采计入报价，不再单列。"""
    original = SoftwareOutsourcingConfigurator.params.fget
    assert original is not None
    monkeypatch.setattr(
        SoftwareOutsourcingConfigurator,
        "params",
        property(lambda self: {**original(self), "third_party_in_quote": True}),
    )
    tier = {t.tier: t for t in cfg().configure(req())}["standard"]
    tp = [i for i in tier.items if i.sku.startswith("TP-")]
    assert {i.sku for i in tp} == {"TP-CLOUD-1Y", "TP-DOMAIN-SSL", "TP-MP-CERT"}
    assert all(i.unit_cost == i.unit_price for i in tp)
    assert tier.specs["cost_breakdown"]["third_party"] == sum(i.total_cost for i in tp)
    assert tier.specs["client_costs"] == []


def test_ai_feature_monthly_cost() -> None:
    """交付的软件带 AI 功能：估算上线后每月的大模型调用费，不计入报价。"""
    plain = {t.tier: t for t in cfg().configure(req())}["standard"]
    assert plain.specs["ai_monthly_cost"] == 0
    mods = [{"key": "ai", "name": "智能客服", "complexity": "medium"}]
    tier = {t.tier: t for t in cfg().configure(req(modules=mods))}["standard"]
    assert tier.specs["ai_monthly_cost"] > 0
    assert "AI 调用费" in tier.summary
    monthly = [c for c in tier.specs["client_costs"] if c["period"] == "month"]
    assert [c["amount"] for c in monthly] == [tier.specs["ai_monthly_cost"]]
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


OCR = [
    {"key": "file", "name": "单据上传"},
    {"key": "ocr", "name": "单据识别", "complexity": "complex"},
    {"key": "workflow", "name": "审核流程"},
]


def test_no_sop_adds_discovery_work() -> None:
    """客户没有 SOP：三档都加业务调研与流程梳理，按产品经理单价、不按研发比例。"""
    plain = cfg().configure(req())
    tiers = cfg().configure(req(no_sop=True))
    for a, b in zip(plain, tiers, strict=True):
        sop = next(i for i in b.items if i.sku == "SVC-SOP")
        assert sop.qty == cfg().params["sop_days"] and sop.unit_price == 180000
        assert b.total_price == a.total_price + sop.total_price
    assert "SOP" in cfg().clarify(req(no_sop=True))["notes"][0]
    assert cfg().clarify(req())["notes"] == []


def test_ocr_monthly_cost_by_pages() -> None:
    """图片识别按每月张数估月费；客户没说量按默认月量，并写明按多少张估。"""
    p = cfg().params
    std = {t.tier: t for t in cfg().configure(req(modules=OCR))}["standard"]
    assert std.specs["ocr_monthly_pages"] == p["ocr_monthly_pages"]
    assert std.specs["ai_monthly_cost"] == p["ocr_monthly_pages"] * p["ocr_cost_per_page"]
    assert f"按每月 {p['ocr_monthly_pages']:,} 张估" in std.summary
    big = {t.tier: t for t in cfg().configure(req(modules=OCR, ocr_monthly_pages=60000))}
    assert big["standard"].specs["ai_monthly_cost"] == 60000 * p["ocr_cost_per_page"]
    assert big["standard"].total_price == std.total_price  # 月费不计入一次性报价


def test_ocr_suggests_poc_on_recommended_tier() -> None:
    tiers = cfg().configure(req(modules=OCR))
    rec = next(t for t in tiers if t.recommended)
    assert "识别验证" in rec.summary
    assert all("识别验证" not in t.summary for t in tiers if not t.recommended)
    poc = cfg().poc(req(modules=OCR))
    assert poc and poc["price"] == cfg().params["poc_days"] * 160000
    assert cfg().poc(req()) is None
    assert any("识别验证" in n for n in cfg().clarify(req(modules=OCR))["notes"])


def test_rule_draft_no_sop_and_ocr_volume() -> None:
    d = cfg().draft_requirement("单据拍照OCR识别，每天大概200票，现在没有SOP文档")
    assert d["no_sop"] is True and d["ocr_monthly_pages"] == 6000
    assert any(m["key"] == "ocr" for m in d["modules"])
    sample = cfg().draft_requirement("客户先给了30张图片样例，要做图片识别")
    assert "ocr_monthly_pages" not in sample and "no_sop" not in sample


def test_clarify_text_shows_notes() -> None:
    from app.agent.nodes.solution import clarify_text

    r = req(modules=OCR, no_sop=True)
    card = {"requirement": r.model_dump(mode="json"), **cfg().clarify(r)}
    text = clarify_text(card)
    assert "> 客户没有现成的 SOP" in text and "识别验证" in text


def test_fill_defaults_platform_only_when_missing() -> None:
    """拆出了功能但没说端：默认网站；已有端（含上一轮草稿的）不覆盖；没有功能不补。"""
    mods = [{"key": "ocr", "name": "单据识别"}]
    assert cfg().fill_defaults({"modules": mods})["platforms"] == ["web"]
    kept = cfg().fill_defaults({"modules": mods, "platforms": ["mini_program"]})
    assert kept["platforms"] == ["mini_program"]
    assert "platforms" not in cfg().fill_defaults({"budget": 100})
