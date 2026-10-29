"""评估脚本的匹配和数字溯源（不调模型）。"""

from app.packs.registry import get_configurator
from evals.run_eval import eval_case, matches, trace_numbers


def test_matches_key_or_name_keyword() -> None:
    his = {"key": "custom", "name": "对接医院 HIS 系统"}
    assert matches("integration|~HIS", his)
    assert matches("integration", {"key": "integration", "name": "对接用友"})
    assert not matches("payment|~支付", his)


def test_trace_numbers_exact_approx_unknown() -> None:
    draft = "- **标准版**：约 93 人天，¥156,000，毛利 44.4%"
    res = trace_numbers("标准版约 15.6 万、毛利 44.4%，大约 15 万；工期 3 档；另需 ¥88,000", draft)
    assert "15.6 万" in res["exact"] and "44.4%" in res["exact"]
    assert "15 万" in res["approx"]
    assert res["unknown"] == ["88,000"]


def test_trace_numbers_derived_from_draft() -> None:
    """档位差价、比例取整算「推算」，不算编造。"""
    draft = "经济版 ¥105,600，毛利 41.4%；标准版 ¥117,200，毛利 43.9%"
    res = trace_numbers("比经济版只多约 1.16 万，毛利都在 41%–44% 之间", draft)
    assert res["derived"] == ["1.16 万", "41%"]
    assert res["exact"] == ["44%"] and res["unknown"] == []


def test_model_failure_is_reported_not_hidden() -> None:
    """模型调用失败时记为「模型失败」，不当成规则结果计入指标。"""
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    class Broken(GenericFakeChatModel):
        def with_structured_output(self, *a: object, **k: object) -> "Broken":
            raise ConnectionError("gateway down")

    cfg = get_configurator("software_outsourcing")
    case = {"id": "x", "text": "做个预约小程序", "platforms": ["mini_program"]}
    r = eval_case(case, cfg, Broken(messages=iter([])), explain=False)  # type: ignore[arg-type]
    assert r.model_failed and "gateway down" in (r.error or "")


def test_rule_mode_case_and_vague() -> None:
    cfg = get_configurator("software_outsourcing")
    case = {
        "id": "x",
        "text": "做个门店预约小程序，要会员登录、在线预约和微信支付，还要管理后台，预算15万",
        "platforms": ["mini_program", "admin"],
        "required": ["booking", "payment", "account"],
        "budget": 150000,
    }
    r = eval_case(case, cfg, None, explain=False)  # type: ignore[arg-type]
    assert r.passed and r.required_hit == 3 and r.quote_ok and r.values_ok
    vague = eval_case({"id": "v", "text": "帮我给客户做个系统", "vague": True}, cfg, None, False)  # type: ignore[arg-type]
    assert vague.passed and vague.missing


def test_regressions_against_baseline() -> None:
    """基线里通过、这次没过算回归；模型没调通单列，不算回归；基线外的用例不管。"""
    from evals.run_eval import CaseResult, regressions

    def res(id_: str, passed: bool, model_failed: bool = False) -> CaseResult:
        r = CaseResult(id=id_, mode="llm", vague=False, seconds=0)
        r.passed, r.model_failed = passed, model_failed
        return r

    baseline = {"llm": ["a", "b", "c"]}
    results = {"llm": [res("a", True), res("b", False), res("c", False, True), res("d", False)]}
    bad, unknown = regressions(baseline, results)
    assert [b.split("：")[0] for b in bad] == ["llm/b"]
    assert unknown == ["llm/c"]
