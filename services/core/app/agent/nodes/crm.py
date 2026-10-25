"""CRM 动作节点（tool_agent ⇄ tools）。

现阶段为规则占位实现：按关键词选择只读 / 低风险工具（search_customer、add_followup、
pipeline_summary、search_policy），保证事件流端到端可跑。
TODO: 改为 llm.bind_tools(TOOLS) + ToolNode 循环（最多 max_tool_calls 次），
      needs_confirm 的写工具（update_opportunity_stage、submit_expense）拆到独立节点并走 interrupt。
"""

from collections.abc import Callable
from typing import Any

from app.agent.deps import AgentDeps
from app.agent.nodes.common import call_tool, log_tool, node_start
from app.agent.state import AgentState

Node = Callable[[AgentState], dict[str, Any]]


def plan_tools(text: str) -> list[str]:
    """根据用户消息挑选要调用的工具（占位规则）。"""
    if any(w in text for w in ("报销", "制度", "标准")):
        return ["search_policy"]
    if any(w in text for w in ("漏斗", "商机统计", "管道")):
        return ["pipeline_summary"]
    steps = ["search_customer"]
    if any(w in text for w in ("跟进", "记一下", "记录")):
        steps.append("add_followup")
    return steps


def _args_for(name: str, text: str, state: AgentState, found: list[dict[str, Any]]) -> dict | None:
    if name == "search_customer":
        return {"keyword": text[:200]}
    if name == "add_followup":
        if len(found) != 1:
            return None  # 没有唯一匹配的客户时不写入，交给用户确认
        return {"customer_id": found[0]["id"], "content": text, "type": "phone"}
    if name == "search_policy":
        return {"query": text[:500], "pack_id": state.get("pack_id")}
    return {}


def make_tool_agent(deps: AgentDeps) -> Node:
    def tool_agent(state: AgentState) -> dict[str, Any]:
        node_start("tool_agent")
        text = state.get("user_message", "")
        log = list(state.get("tool_log", []))
        found: list[dict[str, Any]] = []
        for name in plan_tools(text)[: deps.max_tool_calls]:
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

    return tool_agent
