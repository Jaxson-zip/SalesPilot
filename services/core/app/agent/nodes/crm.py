"""CRM 动作的规则兜底：没有可用模型时，按关键词选择只读工具。

正常情况下由 nodes/tool_loop.py 的 function calling 循环处理；这里只覆盖查客户、
漏斗统计、查制度。写操作（包括记跟进）都要用户确认，规则兜底一律不写库。
"""

from typing import Any

from app.agent.deps import AgentDeps
from app.agent.nodes.common import call_tool, log_tool
from app.agent.state import AgentState


def plan_tools(text: str) -> list[str]:
    """根据用户消息挑选要调用的工具（占位规则）。"""
    if any(w in text for w in ("报销", "制度", "标准")):
        return ["search_policy"]
    if any(w in text for w in ("漏斗", "商机统计", "管道")):
        return ["pipeline_summary"]
    return ["search_customer"]


def _args_for(name: str, text: str, state: AgentState, found: list[dict[str, Any]]) -> dict | None:
    if name == "search_customer":
        return {"keyword": text[:200]}
    if name == "search_policy":
        return {"query": text[:500], "pack_id": state.get("pack_id")}
    return {}


def run_rule_plan(deps: AgentDeps, state: AgentState) -> dict[str, Any]:
    text = state.get("user_message", "")
    log = list(state.get("tool_log", []))
    found: list[dict[str, Any]] = []
    # 学习问答模式只查知识库，不碰客户数据
    names = ["search_policy"] if state.get("mode") == "learn" else plan_tools(text)
    for name in names[: deps.max_tool_calls]:
        args = _args_for(name, text, state, found)
        if args is None:
            continue
        result = call_tool(deps, name, args)
        log = log_tool({**state, "tool_log": log}, name, result)
        if not result.ok:
            break
        if name == "search_customer":
            found = list(result.data or [])
    return {"tool_log": log}
