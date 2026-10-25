"""回复节点：流式输出总结（message.delta）。

有聊天模型时把工具结果作为上下文交给模型解释（数字只能引用工具结果）；
没有模型或网关不可用时，用模板拼出回复，保证链路可用。
"""

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.deps import AgentDeps
from app.agent.nodes.common import emit, node_start
from app.agent.prompts import system_prompt
from app.agent.state import AgentState

logger = logging.getLogger("core.agent")
Node = Callable[[AgentState], dict[str, Any]]


def _yuan(cents: Any) -> str:
    return f"¥{int(cents or 0) / 100:,.0f}"


def template_reply(state: AgentState) -> str:
    """规则模板回复（不依赖大模型）。"""
    if err := state.get("error"):
        return (
            f"处理时出错（{err.get('code')}）：{err.get('message')}。可以稍后重试，或转人工处理。"
        )
    if quote := state.get("quote"):
        price = _yuan(quote["total_price"])
        return f"报价单 {quote['code']} 已创建，总价 {price}，状态：{quote['status']}。"
    if state.get("intent") == "solution":
        return _solution_text(state)
    log = state.get("tool_log", [])
    if log:
        return "已完成：" + "；".join(f"{e['tool']}：{e['summary']}" for e in log) + "。"
    return "你好，我是 SalesPilot。可以帮你记跟进、查客户、出方案报价、算提成和报销。"


def _solution_text(state: AgentState) -> str:
    tiers = state.get("tiers", [])
    lines = [
        f"{t['name']}：{t['summary']}，{_yuan(t['total_price'])}，毛利 {t['margin_rate']:.1%}"
        for t in tiers
    ]
    head = "方案如下：\n" + "\n".join(f"- {line}" for line in lines) if lines else ""
    if state.get("decision") == "reject":
        return f"{head}\n已取消生成报价单。"
    if tiers and not state.get("margin_ok"):
        reason = state.get("margin_reason")
        return (
            f"{head}\n调整 {state.get('retry', 0)} 次后毛利仍不达标（{reason}），"
            "请你决定是否提交主管审批。"
        )
    return head or "方案已生成。"


def _llm_messages(state: AgentState, draft: str) -> list[BaseMessage]:
    context = "\n".join(f"- {e['tool']}：{e['summary']}" for e in state.get("tool_log", []))
    return [
        SystemMessage(content=system_prompt(state.get("pack_id"))),
        *state.get("messages", [])[-10:],
        HumanMessage(content=f"【工具结果，只能引用其中的数字】\n{context}\n【参考回复】\n{draft}"),
    ]


def _stream_llm(deps: AgentDeps, state: AgentState, draft: str) -> str | None:
    if deps.llm is None:
        return None
    parts: list[str] = []
    try:
        for chunk in deps.llm.stream(_llm_messages(state, draft)):
            text = chunk.content if isinstance(chunk.content, str) else ""
            if text:
                parts.append(text)
                emit("message.delta", {"text": text})
    except Exception:
        logger.warning("respond: llm stream failed, fallback to template", exc_info=True)
        if parts:
            return "".join(parts)
        return None
    return "".join(parts)


def make_respond(deps: AgentDeps) -> Node:
    def respond(state: AgentState) -> dict[str, Any]:
        node_start("respond")
        draft = template_reply(state)
        text = _stream_llm(deps, state, draft) if not state.get("error") else None
        if text is None:
            text = draft
            emit("message.delta", {"text": text})
        return {"messages": [AIMessage(content=text)]}

    return respond
