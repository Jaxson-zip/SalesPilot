"""软件外包 AI 评估：拆解准确率、追问判断、数值抽取、报价自洽、方案解释是否编造数字。

用法（在 core 容器里跑，需要网关 Key）：
    python -m evals.run_eval                # 大模型 + 规则兜底两种模式都跑
    python -m evals.run_eval --rule-only    # 只跑规则模式（不调模型，离线可跑）
    python -m evals.run_eval --no-explain   # 不评估方案解释（少一半模型调用）

只调用模型和行业包配置器，不写任何业务数据；评估用的模型不挂用量回调，不计入「AI 用量」。
结果写到 evals/reports/：report.md（给人看）和 results.json（逐条明细）。
"""

import argparse
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent.nodes.requirement_fields import EXTRACT_PROMPT, optional_model
from app.agent.nodes.respond import _explain_messages, explain_draft
from app.agent.tools.solution_tools import missing_fields
from app.packs.registry import get_configurator
from app.packs.software_outsourcing.configurator import (
    CLIENT_PLATFORMS,
    SoftwareOutsourcingConfigurator,
)

PACK = "software_outsourcing"
HERE = Path(__file__).parent
CASES = HERE / "software_cases.yaml"
OUT = HERE / "reports"


# ---------- 匹配 ----------


def matches(spec: str, module: dict[str, Any]) -> bool:
    """spec 形如 "integration|~HIS"：任一候选命中即可（key 相等，或 ~关键词 在名称里）。"""
    for alt in spec.split("|"):
        alt = alt.strip()
        if alt.startswith("~"):
            if alt[1:].lower() in str(module.get("name", "")).lower():
                return True
        elif module.get("key") == alt:
            return True
    return False


def find(spec: str, modules: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((m for m in modules if matches(spec, m)), None)


# ---------- 数字溯源（方案解释不能编造数字） ----------

_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(万|%|％)?")


def numbers(text: str) -> list[tuple[float, str, str]]:
    """抽出文本里的数字：(数值, 类型 amount|pct, 原文)。「15.6 万」换算成 156000。"""
    out = []
    for m in _NUM.finditer(text):
        raw, unit = m.group(1), m.group(2)
        value = float(raw.replace(",", ""))
        if unit == "万":
            out.append((value * 10_000, "amount", m.group(0)))
        elif unit in ("%", "％"):
            out.append((value, "pct", m.group(0)))
        else:
            out.append((value, "amount", m.group(0)))
    return out


def trace_numbers(answer: str, source: str) -> dict[str, list[str]]:
    """把回答里的数字和草稿（唯一允许引用的来源）对照。

    exact：能在草稿里找到（金额误差 ≤ 0.6% 或 1 元，比例误差 ≤ 0.15 个百分点）；
    approx：草稿里有 5% 以内的近似值（例如把 156,000 说成「约 15 万」）；
    derived：由草稿里两个金额相减得到（档位差价），或比例取整（「41%–44%」）；
    unknown：草稿里找不到来源，需要人工复核。≤ 10 的小整数（档位数、序号）不检查。
    """
    allowed = numbers(source)
    amounts = [a for a, k, _ in allowed if k == "amount" and a > 10]
    pcts = [a for a, k, _ in allowed if k == "pct"]
    diffs = [abs(a - b) for i, a in enumerate(amounts) for b in amounts[i + 1 :] if a != b]
    res: dict[str, list[str]] = {k: [] for k in NUMBER_KINDS}
    for value, kind, raw in numbers(answer):
        if kind == "amount" and value <= 10 and value == int(value):
            continue
        if kind == "pct":
            if any(abs(a - value) <= 0.15 for a in pcts):
                res["exact"].append(raw.strip())
            elif any(abs(a - value) < 1 for a in pcts):
                res["derived"].append(raw.strip())
            else:
                res["unknown"].append(raw.strip())
        elif any(abs(a - value) <= max(1, a * 0.006) for a in amounts):
            res["exact"].append(raw.strip())
        elif any(abs(a - value) <= a * 0.05 for a in amounts):
            res["approx"].append(raw.strip())
        elif any(abs(d - value) <= d * 0.05 for d in diffs):
            res["derived"].append(raw.strip())
        else:
            res["unknown"].append(raw.strip())
    return res


NUMBER_KINDS = ("exact", "approx", "derived", "unknown")


def extract(
    llm: BaseChatModel | None, cfg: SoftwareOutsourcingConfigurator, text: str
) -> tuple[dict[str, Any], str | None]:
    """与 requirement_fields.extract_with_llm 相同的抽取，但把模型失败报出来。

    线上抽取失败会静默退回规则；评估时必须区分，否则会把规则结果当成模型结果。
    """
    if llm is None:
        return {}, None
    schema = optional_model(cfg.requirement_model)
    system = f"{EXTRACT_PROMPT}\n{cfg.extract_hint()}"
    try:
        out = llm.with_structured_output(schema, method="function_calling").invoke(
            [SystemMessage(system), HumanMessage(text)]
        )
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:160]}"
    if not isinstance(out, BaseModel):
        return {}, "模型没有返回结构化结果"
    return {k: v for k, v in out.model_dump().items() if v is not None}, None


# ---------- 单条评估 ----------


@dataclass
class CaseResult:
    id: str
    mode: str
    vague: bool
    seconds: float
    passed: bool = False
    model_failed: bool = False
    missing: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    platforms_ok: bool | None = None
    clients_ok: bool | None = None
    required_hit: int = 0
    required_total: int = 0
    required_missed: list[str] = field(default_factory=list)
    later_ok: bool | None = None
    modules: list[dict[str, Any]] = field(default_factory=list)
    extra: int = 0
    extra_marked_inferred: int = 0
    mentioned_marked_ok: int = 0
    questions: int = 0
    values_ok: bool | None = None
    invented_values: list[str] = field(default_factory=list)
    quote_ok: bool | None = None
    quote_problems: list[str] = field(default_factory=list)
    standard_price: int | None = None
    person_days: int | None = None
    explain_numbers: dict[str, list[str]] | None = None
    explain_text: str | None = None
    error: str | None = None


def eval_case(
    case: dict[str, Any],
    cfg: SoftwareOutsourcingConfigurator,
    llm: BaseChatModel | None,
    explain: bool,
) -> CaseResult:
    mode = "llm" if llm else "rule"
    start = time.perf_counter()
    text = case["text"]
    ext, failure = extract(llm, cfg, text)
    if failure:
        failed = CaseResult(id=case["id"], mode=mode, vague=bool(case.get("vague")), seconds=0)
        failed.model_failed, failed.error = True, f"模型调用失败：{failure}"
        failed.seconds = round(time.perf_counter() - start, 1)
        return failed
    merged = {**cfg.draft_requirement(text), **ext}
    missing = missing_fields(cfg.requirement_model, merged)
    r = CaseResult(
        id=case["id"],
        mode=mode,
        vague=bool(case.get("vague")),
        seconds=0,
        missing=missing,
    )
    if r.vague:
        r.passed = bool(missing)  # 期望追问
        r.seconds = round(time.perf_counter() - start, 1)
        return r
    if missing:
        r.error = f"误判为信息不足：缺 {missing}"
        r.seconds = round(time.perf_counter() - start, 1)
        return r

    req = cfg.requirement_model.model_validate(merged)
    mods = [m.model_dump() for m in req.modules]
    r.modules = [{k: m[k] for k in ("key", "name", "complexity", "must", "source")} for m in mods]
    r.platforms = list(req.platforms)
    want = set(case.get("platforms", []))
    r.platforms_ok = set(req.platforms) == want
    r.clients_ok = {p for p in req.platforms if p in CLIENT_PLATFORMS} == {
        p for p in want if p in CLIENT_PLATFORMS
    }

    required = case.get("required", [])
    r.required_total = len(required)
    hit_ids: set[int] = set()
    for spec in required:
        m = find(spec, mods)
        if m is None:
            r.required_missed.append(spec)
            continue
        r.required_hit += 1
        hit_ids.add(id(m))
        r.mentioned_marked_ok += m.get("source") == "mentioned"
    later = case.get("later", [])
    if later:
        found = [find(s, mods) for s in later]
        r.later_ok = all(m is not None and m.get("must") is False for m in found)
    extras = [m for m in mods if id(m) not in hit_ids]
    r.extra = len(extras)
    r.extra_marked_inferred = sum(m.get("source") == "inferred" for m in extras)
    r.questions = len(req.questions)

    # 数值：标注了的要抽对；没提到的不能凭空出现
    checks = {"team_size": None, "budget": None, "deadline_weeks": None}
    ok = True
    for key in checks:
        got = getattr(req, key)
        if key in case:
            expect = case[key] * 100 if key == "budget" else case[key]
            ok &= got == expect
        elif got is not None:
            r.invented_values.append(f"{key}={got}")
            ok = False
    r.values_ok = ok

    # 报价自洽：同样输入两次结果一致、合计 = 明细之和、三档价格递增、毛利不低于底线
    tiers = cfg.configure(req)
    again = cfg.configure(req)
    problems = []
    if [t.model_dump() for t in tiers] != [t.model_dump() for t in again]:
        problems.append("两次计算结果不一致")
    for t in tiers:
        if t.total_price != sum(i.total_price for i in t.items):
            problems.append(f"{t.name} 合计 ≠ 明细之和")
        if t.margin_rate < cfg.rules.margin.floor_rate:
            problems.append(f"{t.name} 毛利 {t.margin_rate:.1%} 低于底线")
    prices = [t.total_price for t in tiers]
    if prices != sorted(prices):
        problems.append("三档价格没有递增")
    r.quote_problems = problems
    r.quote_ok = not problems
    std = tiers[1]
    r.standard_price = std.total_price
    r.person_days = std.specs.get("person_days")

    if explain and llm is not None:
        state: dict[str, Any] = {
            "tiers": [t.model_dump(mode="json") for t in tiers],
            "pack_id": PACK,
            "messages": [],
        }
        draft = explain_draft(state)  # type: ignore[arg-type]
        try:
            msg = llm.invoke(_explain_messages(state, draft))  # type: ignore[arg-type]
            r.explain_text = str(msg.content)
            r.explain_numbers = trace_numbers(r.explain_text, draft)
        except Exception as exc:  # 解释失败不影响其他指标
            r.explain_numbers = None
            r.error = f"解释调用失败：{exc}"

    r.passed = bool(
        r.clients_ok and r.required_hit == r.required_total and r.values_ok and r.quote_ok
    ) and (r.later_ok is not False)
    r.seconds = round(time.perf_counter() - start, 1)
    return r


# ---------- 汇总与报告 ----------


def pct(n: float, d: float) -> str:
    return f"{n / d:.0%}" if d else "—"


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    failed = sum(r.model_failed for r in results)
    results = [r for r in results if not r.model_failed]  # 模型没调通的用例不计入指标
    if not results:
        return {"cases": 0, "model_failed": failed}
    full = [r for r in results if not r.vague]
    ok = [r for r in full if not r.error or r.modules]
    vague = [r for r in results if r.vague]
    extras = sum(r.extra for r in ok)
    hits = sum(r.required_hit for r in ok)
    later = [r for r in ok if r.later_ok is not None]
    exp = [r for r in ok if r.explain_numbers is not None]
    nums = {k: sum(len(r.explain_numbers[k]) for r in exp) for k in NUMBER_KINDS}  # type: ignore[index]
    return {
        "cases": len(results),
        "model_failed": failed,
        "passed": sum(r.passed for r in results),
        "false_vague": sum(1 for r in full if r.error and not r.modules),
        "vague_detected": f"{sum(r.passed for r in vague)}/{len(vague)}",
        "clients_acc": pct(sum(bool(r.clients_ok) for r in ok), len(full)),
        "platforms_acc": pct(sum(bool(r.platforms_ok) for r in ok), len(full)),
        "required_recall": pct(hits, sum(r.required_total for r in full)),
        "later_acc": f"{sum(bool(r.later_ok) for r in later)}/{len(later)}",
        "avg_extra": round(extras / len(ok), 1) if ok else 0,
        "inferred_label_acc": pct(sum(r.extra_marked_inferred for r in ok), extras),
        "mentioned_label_acc": pct(sum(r.mentioned_marked_ok for r in ok), hits),
        "questions_ok": pct(sum(3 <= r.questions <= 5 for r in ok), len(ok)),
        "values_acc": pct(sum(bool(r.values_ok) for r in ok), len(full)),
        "quote_ok": pct(sum(bool(r.quote_ok) for r in ok), len(ok)),
        "explain_cases": len(exp),
        "explain_numbers": nums,
        "avg_seconds": round(sum(r.seconds for r in results) / len(results), 1),
    }


SUMMARY_ROWS = [
    ("cases", "有效用例数"),
    ("model_failed", "模型调用失败（不计入指标）"),
    ("passed", "整条通过"),
    ("vague_detected", "模糊需求正确追问"),
    ("false_vague", "需求清楚却误判为信息不足"),
    ("clients_acc", "客户端识别准确率（不含管理后台）"),
    ("platforms_acc", "交付端完全一致（含管理后台）"),
    ("required_recall", "关键模块召回率"),
    ("later_acc", "「二期再做」识别"),
    ("avg_extra", "平均额外补充的模块数"),
    ("inferred_label_acc", "额外模块标为「AI 推断」的比例"),
    ("mentioned_label_acc", "客户提到的模块标为「客户提到」的比例"),
    ("questions_ok", "确认问题 3–5 个"),
    ("values_acc", "人数 / 预算 / 工期抽取正确且不编造"),
    ("quote_ok", "报价自洽（确定性、合计、递增、毛利）"),
    ("avg_seconds", "平均耗时（秒 / 条）"),
]


def render(by_mode: dict[str, list[CaseResult]], model_name: str) -> str:
    sums = {m: summarize(rs) for m, rs in by_mode.items()}
    modes = list(by_mode)
    head = {"llm": f"大模型（{model_name}）", "rule": "规则兜底（无模型）"}
    lines = [
        "# 软件外包 AI 方案评估报告",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}",
        f"- 用例：`evals/software_cases.yaml`，共 {len(next(iter(by_mode.values())))} 条"
        "（人工标注期望的交付端、关键模块、二期模块、人数 / 预算 / 工期；含 3 条模糊需求）",
        "- 评估口径：只看 AI 能不能把话拆对；人天和价格由配置器计算，只检查它是否自洽。",
        "",
        "## 总览",
        "",
        "| 指标 | " + " | ".join(head[m] for m in modes) + " |",
        "|---|" + "---|" * len(modes),
    ]
    for key, label in SUMMARY_ROWS:
        cells = " | ".join(str(sums[m].get(key, "—")) for m in modes)
        lines.append(f"| {label} | {cells} |")

    if "llm" in sums and sums["llm"].get("explain_cases"):
        n = sums["llm"]["explain_numbers"]
        total = sum(n.values())
        lines += [
            "",
            "## 方案解释的数字溯源",
            "",
            f"对 {sums['llm']['explain_cases']} 条用例让模型解释三档方案，"
            f"把回答里的 {total} 个数字和配置器给出的草稿逐一对照：",
            "",
            f"- 能在草稿里找到：{n['exact']} 个（{pct(n['exact'], total)}）",
            f"- 近似引用（5% 以内，如「约 15 万」）：{n['approx']} 个",
            f"- 推算（档位差价、比例取整，如「比经济版多约 1.16 万」）：{n['derived']} 个",
            f"- 找不到来源，需人工复核：{n['unknown']} 个",
        ]
        flagged = [r for r in by_mode["llm"] if r.explain_numbers and r.explain_numbers["unknown"]]
        for r in flagged:
            lines.append(f"  - `{r.id}`：{'、'.join(r.explain_numbers['unknown'])}")  # type: ignore[index]

    for m in modes:
        lines += [
            "",
            f"## 逐条结果 · {head[m]}",
            "",
            "| 用例 | 结果 | 交付端 | 关键模块 | 额外模块 | 问题数 | 标准版 | 说明 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in by_mode[m]:
            if r.model_failed:
                lines.append(f"| `{r.id}` | ⚠️ | — | — | — | — | — | {r.error} |")
                continue
            if r.vague:
                note = "正确追问" if r.passed else "没有追问，直接拆了"
                lines.append(
                    f"| `{r.id}` | {'✅' if r.passed else '❌'} | — | — | — | — | — | {note} |"
                )
                continue
            notes = []
            if r.error:
                notes.append(r.error)
            if r.required_missed:
                notes.append("漏 " + "、".join(r.required_missed))
            if r.later_ok is False:
                notes.append("二期模块没标出")
            if r.invented_values:
                notes.append("编造 " + "、".join(r.invented_values))
            elif r.values_ok is False:
                notes.append("数值抽取不对")
            if r.clients_ok is False:
                notes.append("端：" + "、".join(r.platforms))
            notes += r.quote_problems
            price = f"¥{r.standard_price / 100:,.0f}" if r.standard_price else "—"
            lines.append(
                f"| `{r.id}` | {'✅' if r.passed else '❌'} | {'✓' if r.clients_ok else '✗'}"
                f" | {r.required_hit}/{r.required_total} | {r.extra} | {r.questions}"
                f" | {price} | {'；'.join(notes) or '—'} |"
            )
    lines += [
        "",
        "## 怎么读这份报告",
        "",
        "- **关键模块召回率**：客户明确说了的功能有没有拆出来，漏了会少报价，是最重要的指标。",
        "- **额外模块**：模型按常识补充的功能（例如约课系统补「消息通知」）。这本身不算错，"
        "但必须标成「AI 推断」，让销售和客户确认；所以看的是标注比例，而不是数量。",
        "- **数字**：人天、价格、毛利都由配置器计算，模型只负责拆解和解释；"
        "「数字溯源」检查的是模型在解释时有没有说出草稿里没有的数字。",
        "- 交付端里「要不要管理后台」本身有歧义，所以单列了不含管理后台的客户端准确率。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rule-only", action="store_true", help="只跑规则模式，不调模型")
    ap.add_argument("--no-explain", action="store_true", help="不评估方案解释")
    ap.add_argument("--only", help="只跑某个用例 id（调试用）")
    args = ap.parse_args()

    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
    cfg = get_configurator(PACK)
    assert isinstance(cfg, SoftwareOutsourcingConfigurator)

    modes: dict[str, BaseChatModel | None] = {"rule": None}
    model_name = "—"
    if not args.rule_only:
        from app.common.config import get_settings
        from app.llm.client import get_chat_model

        # 不挂用量回调：评估调用不计入「AI 用量」统计
        llm = get_chat_model(streaming=False, request_id="eval").model_copy(
            update={"callbacks": None}
        )
        modes = {"llm": llm, **modes}
        model_name = get_settings().llm_default_group

    by_mode: dict[str, list[CaseResult]] = {}
    for mode, llm in modes.items():
        by_mode[mode] = []
        streak = 0
        for c in cases:
            if streak >= 3:  # 连续 3 次模型调用失败：网关或上游不可用，后面的不再跑
                skipped = CaseResult(id=c["id"], mode=mode, vague=bool(c.get("vague")), seconds=0)
                skipped.model_failed, skipped.error = True, "前面连续失败，未运行"
                by_mode[mode].append(skipped)
                continue
            r = eval_case(c, cfg, llm, explain=not args.no_explain)
            streak = streak + 1 if r.model_failed else 0
            by_mode[mode].append(r)
            status = "MODEL-FAIL" if r.model_failed else "PASS" if r.passed else "FAIL"
            print(f"[{mode}] {r.id:<16} {status}  {r.seconds}s", flush=True)

    OUT.mkdir(exist_ok=True)
    report = render(by_mode, model_name)
    (OUT / "report.md").write_text(report, encoding="utf-8")
    detail = {m: [r.__dict__ for r in rs] for m, rs in by_mode.items()}
    (OUT / "results.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    for m, rs in by_mode.items():
        s = summarize(rs)
        print(
            f"{m}: 有效 {s['cases']} 条，通过 {s.get('passed', 0)}，"
            f"关键模块召回 {s.get('required_recall', '—')}，模型失败 {s['model_failed']}"
        )
    print(f"报告：{OUT / 'report.md'}")


if __name__ == "__main__":
    main()
