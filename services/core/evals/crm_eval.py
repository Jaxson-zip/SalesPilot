"""CRM 对话评估：用真实模型跑 AI 助手的状态图，看它转不转出方案、调哪个工具、参数对不对。

用法（本机，网关在 8100、Postgres 在 5432）：
    LLM_GATEWAY_BASE=http://127.0.0.1:8100/v1 uv run python -m evals.crm_eval
    ... --only followup-basic      只跑一条
    ... --check                    与基线对比，有回归时退出码为 1（提交前检查用）
    ... --write-baseline           把这次通过的用例写成新基线

在测试库 crm_test 上跑（每次重建演示数据），每条用例跑到 tool_agent 节点结束就停：
弹出确认卡之前、转入出方案之前，不会写业务数据。评估用的模型不挂用量回调。
结果写到 evals/reports/crm_report.md 和 crm_results.json。
"""

from tests.conftest import _ensure_test_database, _migrate_and_seed  # 先导入：切到测试库

# isort: split
import argparse
import json
import logging
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import service
from app.agent.graph import build_graph
from app.common.auth import Role
from app.common.config import get_settings
from app.crm.services.demo import DEMO_USERS, demo_id

HERE = Path(__file__).parent
CASES = HERE / "crm_cases.yaml"
BASELINE = HERE / "crm_baseline.json"
OUT = HERE / "reports"
RERUNS = 2
ROLES = {"sales": Role.SALES, "manager": Role.MANAGER}


@dataclass
class Outcome:
    id: str
    passed: bool = False
    model_failed: bool = False
    route: str = ""
    action: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    request: str | None = None
    reply: str | None = None
    problems: list[str] = field(default_factory=list)
    seconds: float = 0


class _FailureWatch(logging.Handler):
    """tool_agent 调模型失败会静默退回规则；评估要把这种情况单独报出来，不算成模型的结果。"""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.failed = False

    def emit(self, record: logging.LogRecord) -> None:
        if "llm failed" in record.getMessage():
            self.failed = True


# ---------- 期望值 ----------


def resolve(value: Any) -> list[str]:
    """期望值可写成 "customer:mingli|opp:mingli"：任一候选命中即可；seed key 换成 id。"""
    out = []
    for alt in str(value).split("|"):
        alt = alt.strip()
        prefix = alt.split(":", 1)[0]
        out.append(str(demo_id(alt)) if prefix in ("customer", "opp", "contact") else alt)
    return out


def check(case: dict[str, Any], o: Outcome) -> list[str]:
    exp = case["expect"]
    problems = []
    if (route := exp.get("route")) and o.route != route:
        problems.append(f"流程应为 {route}，实际 {o.route}")
    if o.route in exp.get("not", []):
        problems.append(f"不该走 {o.route}")
    if (action := exp.get("action")) and o.action != action:
        problems.append(f"确认卡应为 {action}，实际 {o.action}")
    for key, want in (exp.get("args") or {}).items():
        if str(o.args.get(key)) not in resolve(want):
            problems.append(f"参数 {key} 应为 {want}，实际 {o.args.get(key)}")
    for key in exp.get("args_present") or []:
        if not o.args.get(key):
            problems.append(f"参数里应有 {key}")
    for key in exp.get("args_absent") or []:
        if o.args.get(key):
            problems.append(f"参数里不该有 {key}：{o.args.get(key)}")
    if (tools := exp.get("tools")) and not set(tools) & set(o.tools):
        problems.append(f"应调用 {'/'.join(tools)}，实际 {o.tools or '无'}")
    for word in exp.get("request_has") or []:
        if word not in (o.request or ""):
            problems.append(f"整理的需求里没有「{word}」")
    return problems


# ---------- 运行一条 ----------


def _history(case: dict[str, Any]) -> list[BaseMessage]:
    return [
        HumanMessage(text) if who == "user" else AIMessage(text)
        for who, text in case.get("history") or []
    ]


def _outcome(case_id: str, update: dict[str, Any]) -> Outcome:
    o = Outcome(id=case_id)
    pending = update.get("pending_call")
    o.tools = [t["tool"] for t in update.get("tool_log") or []]
    if update.get("intent") == "solution":
        o.route, o.request = "solution", update.get("solution_request")
    elif pending:
        o.route, o.action, o.args = "write", pending["name"], dict(pending["args"])
    else:
        o.route = "read" if o.tools else "reply"
        o.reply = update.get("agent_reply")
    return o


def run_case(case: dict[str, Any]) -> Outcome:
    start = time.perf_counter()
    user = DEMO_USERS[ROLES[case.get("role", "sales")]]
    thread_id = f"eval-{uuid.uuid4().hex[:12]}"
    deps = service.build_deps(user, thread_id, "eval", None)
    if deps.llm is None:
        return Outcome(id=case["id"], model_failed=True, problems=["网关里没有可用模型"])
    deps.llm = deps.llm.model_copy(update={"callbacks": None})
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
    if case.get("history") or case.get("state"):
        values = {"messages": _history(case), "user_id": str(user.id), **(case.get("state") or {})}
        build_graph(deps, saver).update_state(config, values, as_node="respond")
    opp = demo_id(f"opp:{case['opp']}") if case.get("opp") else None
    run = service.prepare_chat(deps, case["text"], opp, checkpointer=saver)
    watch = _FailureWatch()
    logging.getLogger("core.agent").addHandler(watch)
    update: dict[str, Any] = {}
    try:
        for chunk in run.graph.stream(run.payload, run.config, stream_mode="updates"):
            if "tool_agent" in chunk:
                update = chunk["tool_agent"] or {}
                break
    finally:
        logging.getLogger("core.agent").removeHandler(watch)
    o = _outcome(case["id"], update)
    o.seconds = round(time.perf_counter() - start, 1)
    if watch.failed:
        o.model_failed, o.problems = True, ["模型调用失败，走了规则兜底"]
        return o
    o.problems = check(case, o)
    o.passed = not o.problems
    return o


def run_all(cases: list[dict[str, Any]], confirm: bool) -> list[Outcome]:
    results = []
    for c in cases:
        o = run_case(c)
        if confirm and not o.passed and not o.model_failed:
            # 模型输出有随机性：失败的再跑 RERUNS 次，都通过才算偶发
            reruns = [run_case(c) for _ in range(RERUNS)]
            print(f"  {c['id']} 复跑 {RERUNS} 次通过 {sum(r.passed for r in reruns)} 次")
            if all(r.passed for r in reruns):
                o = reruns[-1]
        status = "MODEL-FAIL" if o.model_failed else "PASS" if o.passed else "FAIL"
        note = f"  {'；'.join(o.problems)}" if o.problems else ""
        print(f"{o.id:<26} {status:<10} {o.seconds}s{note}", flush=True)
        results.append(o)
    return results


# ---------- 报告与基线 ----------


def _detail(o: Outcome) -> str:
    if o.route == "write":
        return f"{o.action} {json.dumps(o.args, ensure_ascii=False, default=str)[:120]}"
    if o.route == "solution":
        return f"需求：{(o.request or '（原话）')[:80]}"
    if o.route == "read":
        return "、".join(o.tools)
    return (o.reply or "")[:60].replace("\n", " ")


def render(results: list[Outcome], model: str) -> str:
    ran = [r for r in results if not r.model_failed]
    ok = sum(r.passed for r in ran)
    lines = [
        "# CRM 对话评估报告",
        "",
        f"- 模型：`{model}`；用例 {len(results)} 条，通过 {ok}/{len(ran)}"
        + (f"，模型没调通 {len(results) - len(ran)} 条" if len(ran) < len(results) else ""),
        "- 每条只跑到 AI 决定「转出方案 / 弹确认卡 / 查资料 / 直接回答」为止，不写数据。",
        "",
        "| 用例 | 结果 | 流程 | 内容 | 问题 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        mark = "⚠️" if r.model_failed else "✅" if r.passed else "❌"
        detail = _detail(r).replace("|", "/")
        lines.append(f"| `{r.id}` | {mark} | {r.route} | {detail} | {'；'.join(r.problems)} |")
    return "\n".join(lines) + "\n"


def check_baseline(results: list[Outcome]) -> int:
    if not BASELINE.exists():
        print("没有基线（evals/crm_baseline.json），先运行 --write-baseline")
        return 1
    expected = set(json.loads(BASELINE.read_text(encoding="utf-8")))
    unknown = [r.id for r in results if r.id in expected and r.model_failed]
    bad = [r for r in results if r.id in expected and not r.model_failed and not r.passed]
    if unknown:
        print(f"⚠️ 模型没调通，{len(unknown)} 条用例未检查：{'、'.join(unknown[:5])}")
    if bad:
        print("❌ CRM 对话评估回归（基线里通过、这次没过）：")
        for r in bad:
            print(f"  - {r.id}：{'；'.join(r.problems)}")
        print("修好后再提交；确认是有意的变化时运行 --write-baseline 更新基线")
        return 1
    print("✅ CRM 对话评估没有回归")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="只跑某个用例 id（调试用）")
    ap.add_argument("--check", action="store_true", help="与基线对比，有回归时退出码为 1")
    ap.add_argument("--write-baseline", action="store_true", help="把这次通过的用例写成新基线")
    args = ap.parse_args()

    if not _ensure_test_database():
        sys.exit("连不上 Postgres（需要 docker compose up -d db）")
    _migrate_and_seed()
    get_settings().wecom_webhook_url = None  # 评估绝不推送企业微信
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
    results = run_all(cases, confirm=args.check or args.write_baseline)

    OUT.mkdir(exist_ok=True)
    report = render(results, get_settings().llm_default_group)
    (OUT / "crm_report.md").write_text(report, encoding="utf-8", newline="\n")
    dump = json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2, default=str)
    (OUT / "crm_results.json").write_text(dump, encoding="utf-8", newline="\n")
    print(f"\n报告：{OUT / 'crm_report.md'}")

    if args.write_baseline:
        ids = sorted(r.id for r in results if r.passed)
        BASELINE.write_text(json.dumps(ids, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"基线已更新：{len(ids)} 条")
    if args.check:
        sys.exit(check_baseline(results))


if __name__ == "__main__":
    main()
