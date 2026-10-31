"""入口节点：只按确定的信号分流，不单独做意图分类。

- 界面上的明确动作（学习问答模式、需求卡片确认、上传样例、上传材料）直接定去向；
- 其余每句话交给对话循环（tool_agent）：模型带着完整上下文判断，要出方案时调用 start_solution；
- 没有模型时用关键词规则分流（离线可用，写操作仍然不会执行）。
"""

from collections.abc import Callable
from typing import Any

from app.agent.deps import AgentDeps
from app.agent.nodes.common import node_start
from app.agent.state import AgentState, Intent, turn_reset

SOLUTION_WORDS = (
    "方案", "部署", "配置", "报价", "采购", "私有化", "选型", "显存", "小程序", "定制开发", "估价",
)  # fmt: skip
CRM_WORDS = ("跟进", "记一下", "记录", "客户", "商机", "阶段", "报销", "提成", "漏斗", "制度")


def classify_intent(text: str, pending_requirement: bool = False) -> Intent:
    """关键词规则：没有模型、或模型第一次调用就失败时使用。"""
    if any(w in text for w in SOLUTION_WORDS):
        return "solution"
    if pending_requirement:
        return "solution"  # 上一轮在追问需求，本轮视为补充信息
    if any(w in text for w in CRM_WORDS):
        return "crm_action"
    return "chitchat"


def entry_intent(deps: AgentDeps, state: AgentState) -> Intent:
    if state.get("mode") == "learn":
        return "crm_action"  # 学习问答：只走知识类工具
    if state.get("confirmed_requirement") or state.get("samples"):
        return "solution"  # 需求卡片确认 / 上传了客户样例：直接出方案
    if state.get("material"):
        return "crm_action"  # 上传了材料：整理写入
    if deps.llm is None:
        return classify_intent(state.get("user_message", ""), bool(state.get("missing")))
    return "crm_action"  # 交给对话循环，由模型判断（要出方案时调用 start_solution）


def make_router(deps: AgentDeps) -> Callable[[AgentState], dict[str, Any]]:
    def router(state: AgentState) -> dict[str, Any]:
        node_start("router")
        intent = entry_intent(deps, state)
        return {**turn_reset(), "intent": intent, "prev_missing": list(state.get("missing") or [])}

    return router


def route_intent(state: AgentState) -> str:
    return {"solution": "parse_requirement", "crm_action": "tool_agent"}.get(
        state.get("intent", "chitchat"), "respond"
    )
