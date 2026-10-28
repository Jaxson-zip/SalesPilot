"""回复节点：流式输出总结（message.delta）。

有聊天模型时把工具结果作为上下文交给模型解释（数字只能引用工具结果）；
没有模型或网关不可用时，用模板拼出回复，保证链路可用。
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.deps import AgentDeps
from app.agent.nodes.common import emit, node_start, now_iso
from app.agent.nodes.solution import recommended_tier
from app.agent.prompts import system_prompt
from app.agent.state import AgentState
from app.crm.schemas.quote import QUOTE_STATUS_LABELS

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
        status = QUOTE_STATUS_LABELS.get(quote["status"], quote["status"])
        return f"报价单 {quote['code']} 已创建，总价 {price}，状态：{status}。"
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


def turn_artifacts(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """本轮推送过的 artifact（与 SSE 的 artifact 事件一致），存进 AIMessage 供会话历史还原。"""
    arts: list[dict[str, Any]] = []
    tiers = state.get("tiers") or []
    if state.get("intent") == "solution" and tiers:
        arts.append({"type": "solution_tiers", "data": tiers})
        arts.append({"type": "bom", "data": recommended_tier(tiers)})
    if quote := state.get("quote"):
        arts.append({"type": "quote", "data": quote})
    refs = [r for e in state.get("tool_log") or [] for r in e.get("sources", [])]
    if refs:
        unique = list({r["title"]: r for r in refs}.values())
        arts.append({"type": "sources", "data": unique})
    return arts


def _llm_messages(state: AgentState, draft: str) -> list[BaseMessage]:
    context = "\n".join(f"- {e['tool']}：{e['summary']}" for e in state.get("tool_log", []))
    return [
        SystemMessage(content=system_prompt(state.get("pack_id"))),
        *state.get("messages", [])[-10:],
        HumanMessage(content=f"【工具结果，只能引用其中的数字】\n{context}\n【参考回复】\n{draft}"),
    ]


def _stream_llm(deps: AgentDeps, state: AgentState, draft: str) -> str | None:
    return _stream(deps, _llm_messages(state, draft))


def _stream(deps: AgentDeps, messages: list[BaseMessage]) -> str | None:
    """流式调用模型并推送 message.delta；没有模型或一个字都没出来就失败时返回 None（用模板）。"""
    if deps.llm is None:
        return None
    parts: list[str] = []
    try:
        for chunk in deps.llm.stream(messages):
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


def explain_draft(state: AgentState) -> str:
    """确认前的方案说明（模板）：各档价格、推荐档位和理由。"""
    tiers = state.get("tiers", [])
    best = recommended_tier(tiers)
    lines = "\n".join(
        f"- **{t['name']}**：{t['summary']}，{_yuan(t['total_price'])}，毛利 {t['margin_rate']:.1%}"
        for t in tiers
    )
    customer = state.get("customer_name")
    head = (
        f"按需求为{customer}出了 {len(tiers)} 档方案："
        if customer
        else f"按需求出了 {len(tiers)} 档方案："
    )
    tail = f"推荐 **{best.get('name')}**：{best.get('summary')}。确认下面的信息后，我来生成报价单。"
    return f"{head}\n{lines}\n\n{tail}"


def _explain_messages(state: AgentState, draft: str) -> list[BaseMessage]:
    return [
        SystemMessage(content=system_prompt(state.get("pack_id"))),
        *state.get("messages", [])[-6:],
        HumanMessage(
            content=(
                "【方案草稿，数字只能引用其中的】\n"
                f"{draft}\n"
                "请用 3–5 句话向销售说明：几档方案的主要差别、推荐哪一档以及原因"
                "（结合并发、预算等需求）。最后一句提示确认后生成报价单。不要使用表格。"
            )
        ),
    ]


def make_explain(deps: AgentDeps) -> Node:
    """确认前流式输出方案说明：确认卡片出现前先有文字逐字出来，而不是卡片一下子全部弹出。

    单独成节点：resume 从 confirm 继续，不会重复输出这段话。
    """

    def explain(state: AgentState) -> dict[str, Any]:
        node_start("explain")
        draft = explain_draft(state)
        text = _stream(deps, _explain_messages(state, draft))
        if text is None:
            text = draft
            emit("message.delta", {"text": text})
        extra = {"artifacts": turn_artifacts(state), "created_at": now_iso()}
        return {"messages": [AIMessage(content=text, additional_kwargs=extra)]}

    return explain


def make_respond(deps: AgentDeps) -> Node:
    def respond(state: AgentState) -> dict[str, Any]:
        node_start("respond")
        # function calling 循环里模型已经流式输出过回复，直接保存，不再生成第二遍
        if reply := state.get("agent_reply"):
            extra = {"artifacts": turn_artifacts(state), "created_at": now_iso()}
            return {"messages": [AIMessage(content=reply, additional_kwargs=extra)]}
        draft = template_reply(state)
        text = _stream_llm(deps, state, draft) if not state.get("error") else None
        if text is None:
            text = draft
            emit("message.delta", {"text": text})
        extra = {"artifacts": turn_artifacts(state), "created_at": now_iso()}
        return {"messages": [AIMessage(content=text, additional_kwargs=extra)]}

    return respond
