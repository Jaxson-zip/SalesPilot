"""Agent 状态（LangGraph）。只放可 JSON 序列化的数据，便于 Postgres checkpointer 持久化。"""

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Intent = Literal["chitchat", "crm_action", "solution"]


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str  # 会话归属，resume 时校验
    user_message: NotRequired[str]
    opportunity_id: NotRequired[str | None]
    intent: NotRequired[Intent]
    pack_id: NotRequired[str | None]
    requirement: NotRequired[dict[str, Any]]  # 跨轮次累积的需求草稿
    missing: NotRequired[list[str]]
    tiers: NotRequired[list[dict[str, Any]]]
    margin_ok: NotRequired[bool]
    margin_reason: NotRequired[str]
    retry: NotRequired[int]
    hint: NotRequired[str | None]
    decision: NotRequired[str | None]
    quote: NotRequired[dict[str, Any] | None]
    tool_log: NotRequired[list[dict[str, Any]]]  # 本轮工具结果摘要，respond 用
    error: NotRequired[dict[str, Any] | None]


def turn_reset() -> dict[str, Any]:
    """每轮开始时清空的字段（requirement 保留，用于多轮补充需求）。"""
    return {
        "intent": "chitchat",
        "missing": [],
        "tiers": [],
        "margin_ok": False,
        "margin_reason": "",
        "retry": 0,
        "hint": None,
        "decision": None,
        "quote": None,
        "tool_log": [],
        "error": None,
    }
