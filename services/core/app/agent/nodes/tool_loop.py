"""CRM 动作：大模型 function calling 循环（场景 3：自然语言 → 意图 → 工具调用 → 汇总回复）。

    tool_agent ──(模型要调写工具)──▶ confirm_action（interrupt）──▶ run_action ──▶ tool_agent
        │                                                                    （把结果交回模型继续）
        └──(模型不再调工具 / 达到上限)──▶ respond

- 模型只能看到当前角色可用的工具（chat_tools_for）；幂等键、行业包由系统注入，不由模型生成。
- 只读工具直接执行；needs_confirm 的写工具先停下来等用户确认，一次只确认一个。
- 没有可用模型（deps.llm 为 None）或第一次调用模型就失败时，回落到关键词规则（nodes/crm.py）。
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.types import interrupt

from app.agent.deps import AgentDeps
from app.agent.nodes.common import call_tool, emit, log_tool, node_start
from app.agent.nodes.crm import run_rule_plan
from app.agent.prompts import system_prompt
from app.agent.state import AgentState
from app.agent.tools import TOOLS, ToolResult, chat_tools_for, inject_system_args
from app.agent.tools.previews import confirm_preview
from app.rules.crm_calc import LOCAL_TZ

logger = logging.getLogger("core.agent")
Node = Callable[[AgentState], dict[str, Any]]

TOOL_RULES = """
## 调用工具的规则
- 今天是 {today}（北京时间），当前用户：{user}（{role}）。
- 需要客户、商机、联系人的 id 时，先调用 search_customer、get_customer_context 查询，禁止编造 id。
- search_customer 匹配到多个客户时，列出候选让用户选，不要自己挑。
- 金额参数一律以「分」为单位（860 元 = 86000）。
- 信息不全（例如报销没说金额、日期）时先问用户，不要猜。
- 写操作（改阶段、提交报销、建任务、审批）会弹出确认卡片，用户确认后才执行。
""".strip()


def _system(deps: AgentDeps, state: AgentState) -> SystemMessage:
    user = deps.ctx.user
    rules = TOOL_RULES.format(
        today=datetime.now(LOCAL_TZ).date().isoformat(), user=user.name, role=user.role.value
    )
    return SystemMessage(content=f"{system_prompt(state.get('pack_id'))}\n\n{rules}")


def _tool_content(result: ToolResult) -> str:
    """工具结果回传给模型：结构化 JSON（ok / summary / data / error）。"""
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, default=str)


def _stream_round(deps: AgentDeps, messages: list[BaseMessage]) -> AIMessage:
    """调用一次模型（流式），正文实时推送 message.delta，工具调用片段累积成完整的 tool_calls。"""
    assert deps.llm is not None
    schemas = [t.openai_schema() for t in chat_tools_for(deps.ctx.user.role)]
    acc: AIMessageChunk | None = None
    for chunk in deps.llm.bind_tools(schemas).stream(messages):
        if not isinstance(chunk, AIMessageChunk):
            continue
        if isinstance(chunk.content, str) and chunk.content:
            emit("message.delta", {"text": chunk.content})
        acc = chunk if acc is None else acc + chunk
    if acc is None:
        return AIMessage(content="")
    content = acc.content if isinstance(acc.content, str) else ""
    return AIMessage(content=content, tool_calls=acc.tool_calls, id=acc.id)


def _allowed(deps: AgentDeps) -> set[str]:
    return {t.name for t in chat_tools_for(deps.ctx.user.role)}


def _system_args(deps: AgentDeps, state: AgentState, call_id: str) -> dict[str, Any]:
    pack = state.get("pack_id") or deps.ctx.default_pack
    return {"idempotency_key": f"agent:{deps.ctx.thread_id}:{call_id}", "pack_id": pack}


def _skip(call_id: str, reason: str) -> ToolMessage:
    return ToolMessage(
        content=json.dumps({"ok": False, "summary": reason}, ensure_ascii=False),
        tool_call_id=call_id,
    )


def _run_calls(
    deps: AgentDeps, state: AgentState, ai: AIMessage, messages: list[AnyMessage], log: list
) -> tuple[dict[str, Any] | None, list]:
    """执行一轮 tool_calls：只读直接执行；遇到需要确认的写工具就停下（返回 pending）。"""
    pending: dict[str, Any] | None = None
    allowed = _allowed(deps)
    for call in ai.tool_calls:
        call_id = call.get("id") or ""
        name = call["name"]
        if pending is not None:
            messages.append(_skip(call_id, "未执行：一次只处理一个需要确认的操作，确认后再发起"))
            continue
        if name not in allowed:
            messages.append(_skip(call_id, f"当前角色不能使用工具 {name}"))
            continue
        spec = TOOLS[name]
        raw = dict(call.get("args") or {})
        args = inject_system_args(spec, raw, _system_args(deps, state, call_id))
        if spec.needs_confirm:
            preview = confirm_preview(deps.ctx, name, args)
            pending = {"id": call_id, "name": name, "args": args, "preview": preview}
            continue
        result = call_tool(deps, name, args)
        log = log_tool({**state, "tool_log": log}, name, result)
        messages.append(ToolMessage(content=_tool_content(result), tool_call_id=call_id))
    return pending, log


def _initial_messages(deps: AgentDeps, state: AgentState) -> list[AnyMessage]:
    history = [m for m in state.get("messages", [])[-12:] if not isinstance(m, ToolMessage)]
    return [_system(deps, state), *history]


def _llm_loop(deps: AgentDeps, state: AgentState) -> dict[str, Any]:
    messages: list[AnyMessage] = list(state.get("scratch") or _initial_messages(deps, state))
    log = list(state.get("tool_log", []))
    rounds = state.get("tool_rounds", 0)
    said = [state["agent_reply"]] if state.get("agent_reply") else []
    while rounds < deps.max_tool_calls:
        ai = _stream_round(deps, messages)
        messages.append(ai)
        if isinstance(ai.content, str) and ai.content:
            said.append(ai.content)
        if not ai.tool_calls:
            break
        rounds += 1
        pending, log = _run_calls(deps, state, ai, messages, log)
        if pending is not None:
            out = {"scratch": messages, "tool_log": log, "tool_rounds": rounds}
            return {**out, "pending_call": pending, "agent_reply": "".join(said) or None}
    return {
        "scratch": messages,
        "tool_log": log,
        "tool_rounds": rounds,
        "pending_call": None,
        "agent_reply": "".join(said) or None,
    }


def make_tool_agent(deps: AgentDeps) -> Node:
    def tool_agent(state: AgentState) -> dict[str, Any]:
        node_start("tool_agent")
        if deps.llm is None:
            return run_rule_plan(deps, state)
        try:
            return _llm_loop(deps, state)
        except Exception:
            logger.warning("tool_agent: llm failed", exc_info=True)
            if not state.get("scratch"):
                return run_rule_plan(deps, state)  # 第一次就失败：按规则兜底
            return {"pending_call": None}  # 中途失败：用已有的工具结果出模板回复

    return tool_agent


def route_after_tool_agent(state: AgentState) -> str:
    return "confirm_action" if state.get("pending_call") else "respond"


def make_confirm_action(deps: AgentDeps) -> Node:
    def confirm_action(state: AgentState) -> dict[str, Any]:
        """写操作前中断。resume 时本节点会重跑，interrupt 之前不能有副作用。

        预览已在 tool_agent 里算好，这里只读 state。
        """
        call = state["pending_call"] or {}
        decision = interrupt({"action": call.get("name"), "preview": call.get("preview", {})})
        return {"decision": str(decision)}

    return confirm_action


def make_run_action(deps: AgentDeps) -> Node:
    def run_action(state: AgentState) -> dict[str, Any]:
        """执行（或取消）确认过的写操作，把结果作为 ToolMessage 交回模型继续。"""
        node_start("run_action")
        call = state["pending_call"] or {}
        messages = list(state.get("scratch", []))
        if state.get("decision") == "approve":
            result = call_tool(deps, call["name"], call["args"])
        else:
            result = ToolResult(ok=False, summary="用户取消了该操作，没有写入任何数据")
        log = log_tool(state, call["name"], result)
        messages.append(ToolMessage(content=_tool_content(result), tool_call_id=call["id"]))
        return {"scratch": messages, "tool_log": log, "pending_call": None}

    return run_action
