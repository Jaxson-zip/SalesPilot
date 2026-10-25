"""意图路由节点。

现阶段用关键词规则（离线可测、结果稳定）。
TODO: 网关可用时改为大模型结构化输出分类，规则作为兜底。
"""

from collections.abc import Callable
from typing import Any

from app.agent.deps import AgentDeps
from app.agent.nodes.common import node_start
from app.agent.state import AgentState, Intent, turn_reset

SOLUTION_WORDS = ("方案", "部署", "配置", "报价", "采购", "私有化", "选型", "显存")
CRM_WORDS = ("跟进", "记一下", "记录", "客户", "商机", "阶段", "报销", "提成", "漏斗", "制度")


def classify_intent(text: str, pending_requirement: bool = False) -> Intent:
    if any(w in text for w in SOLUTION_WORDS):
        return "solution"
    if pending_requirement:
        return "solution"  # 上一轮在追问需求，本轮视为补充信息
    if any(w in text for w in CRM_WORDS):
        return "crm_action"
    return "chitchat"


def make_router(deps: AgentDeps) -> Callable[[AgentState], dict[str, Any]]:
    def router(state: AgentState) -> dict[str, Any]:
        node_start("router")
        pending = bool(state.get("missing"))
        intent = classify_intent(state.get("user_message", ""), pending)
        return {**turn_reset(), "intent": intent}

    return router


def route_intent(state: AgentState) -> str:
    return {"solution": "parse_requirement", "crm_action": "tool_agent"}.get(
        state.get("intent", "chitchat"), "respond"
    )
