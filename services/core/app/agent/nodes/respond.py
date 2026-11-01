"""回复节点：流式输出总结（message.delta）。

有聊天模型时把工具结果作为上下文交给模型解释（数字只能引用工具结果）；
没有模型或网关不可用时，用模板拼出回复，保证链路可用。
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.action_result import contradicts, status_text
from app.agent.deps import AgentDeps
from app.agent.nodes.common import emit, emit_notice, node_start, now_iso
from app.agent.nodes.solution import recommended_tier
from app.agent.prompts import system_prompt
from app.agent.runtime import model_text, now_text, runtime_note
from app.agent.state import AgentState
from app.crm.schemas.quote import QUOTE_STATUS_LABELS

logger = logging.getLogger("core.agent")
Node = Callable[[AgentState], dict[str, Any]]


def _yuan(cents: Any) -> str:
    return f"¥{int(cents or 0) / 100:,.0f}"


CHITCHAT_RULE = """
## 闲聊和业务以外的问题
直接回答用户这句话本身，简短、如实：时间、日期、你是什么模型按上面的运行信息回答；
不知道的就说不知道，不要编。和销售工作无关的问题答完即可，不必每次都介绍自己能做什么。
""".strip()

TIME_WORDS = ("几点", "时间", "几号", "日期", "星期几", "周几", "今天是")
MODEL_WORDS = ("什么模型", "哪个模型", "什么大模型", "用的模型", "你是谁", "谁做的", "谁开发")


def rule_chitchat(text: str) -> str | None:
    """没有模型时的闲聊兜底：问模型、问时间给真实答案；其它返回 None（用默认问候）。"""
    if any(w in text for w in MODEL_WORDS):
        return "我是 SalesPilot 里的 AI 助手。" + model_text(None)
    if any(w in text for w in TIME_WORDS):
        return f"现在是 {now_text()}。"
    return None


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
    if state.get("intent", "chitchat") == "chitchat" and (
        rule := rule_chitchat(state.get("user_message", ""))
    ):
        return rule
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
    if res := state.get("action_result"):
        arts.append({"type": "action_result", "data": res})
    refs = [r for e in state.get("tool_log") or [] for r in e.get("sources", [])]
    if refs:
        unique = list({r["title"]: r for r in refs}.values())
        arts.append({"type": "sources", "data": unique})
    return arts


def _system(state: AgentState, note: str, *extra: str) -> SystemMessage:
    parts = [system_prompt(state.get("pack_id")), note, *extra]
    return SystemMessage(content="\n\n".join(p for p in parts if p))


def is_chitchat(state: AgentState) -> bool:
    return (
        state.get("intent", "chitchat") == "chitchat"
        and not state.get("tool_log")
        and not state.get("error")
        and not state.get("quote")
    )


def _chat_messages(state: AgentState, note: str) -> list[BaseMessage]:
    """闲聊：不给固定的参考回复（否则模型会照着它复述自我介绍），让模型直接回答这句话。"""
    return [_system(state, note, CHITCHAT_RULE), *state.get("messages", [])[-10:]]


# 出方案链路的步骤用中文名交给模型：原来给的是函数名，回复里会写出「已通过 check_margin 校验」
STEP_LABELS = {
    "parse_requirement": "理解需求",
    "configure_solution": "配置方案",
    "check_margin": "毛利校验",
    "generate_quote": "生成报价单",
}


def _llm_messages(state: AgentState, draft: str, note: str = "") -> list[BaseMessage]:
    context = "\n".join(
        f"- {STEP_LABELS.get(e['tool'], e['tool'])}：{e['summary']}"
        for e in state.get("tool_log", [])
    )
    head = "【工具结果，只能引用其中的数字；回复里不要写工具名或英文函数名】"
    return [
        _system(state, note),
        *state.get("messages", [])[-10:],
        HumanMessage(content=f"{head}\n{context}\n【参考回复】\n{draft}"),
    ]


def _stream_llm(deps: AgentDeps, state: AgentState, draft: str) -> str | None:
    note = runtime_note(deps.model)
    if is_chitchat(state):
        return _stream(deps, _chat_messages(state, note))
    return _stream(deps, _llm_messages(state, draft, note))


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


def _explain_messages(state: AgentState, draft: str, note: str = "") -> list[BaseMessage]:
    return [
        _system(state, note),
        *state.get("messages", [])[-6:],
        HumanMessage(
            content=(
                "【方案草稿，数字只能引用其中的】\n"
                f"{draft}\n"
                "请用 3–5 句话向销售说明：几档方案的主要差别，以及为什么推荐草稿里的推荐档"
                "（结合客户的需求和预算）。推荐档由系统按预算定好，也是生成报价单默认选中的档位，"
                "不要改推荐别的档；超出预算时如实说明差额。最后一句提示确认后生成报价单。不要使用表格。"
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
        head = emit_notice(state)
        text = _stream(deps, _explain_messages(state, draft, runtime_note(deps.model)))
        if text is None:
            text = draft
            emit("message.delta", {"text": text})
        text = head + text
        extra = {"artifacts": turn_artifacts(state), "created_at": now_iso()}
        return {"messages": [AIMessage(content=text, additional_kwargs=extra)]}

    return explain


def make_respond(deps: AgentDeps) -> Node:
    def respond(state: AgentState) -> dict[str, Any]:
        node_start("respond")
        res = state.get("action_result")
        reply = state.get("agent_reply")
        if res and (not reply or contradicts(reply, res)):
            # 确认后的写操作：按执行状态回复（模型没说话，或已写入却还在让用户确认）
            reply = status_text(res)
            emit("message.replace", {"text": reply})
        # function calling 循环里模型已经流式输出过回复，直接保存，不再生成第二遍
        if reply:
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
