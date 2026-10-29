"""意图路由节点：有模型时用大模型结构化输出分类，失败或没有模型时用关键词规则兜底。"""

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.deps import AgentDeps
from app.agent.nodes.common import node_start
from app.agent.state import AgentState, Intent, turn_reset

logger = logging.getLogger("core.agent")

ROUTER_PROMPT = """你是 CRM 助手的意图分类器，只输出分类结果。
- solution：要出方案、配置、报价、选型、估算算力或开发工作量，
  或在补充方案需求（模型、并发、预算、要做的功能 / 端、交付人数等）
- crm_action：查客户 / 商机、记跟进、改商机阶段、安排任务、报销、算提成、审批、问公司制度
- chitchat：打招呼、闲聊、问你能做什么"""


class IntentDecision(BaseModel):
    """用户这句话的意图。"""

    intent: Intent = Field(description="solution / crm_action / chitchat")


SOLUTION_WORDS = (
    "方案", "部署", "配置", "报价", "采购", "私有化", "选型", "显存", "小程序", "定制开发", "估价",
)  # fmt: skip
CRM_WORDS = ("跟进", "记一下", "记录", "客户", "商机", "阶段", "报销", "提成", "漏斗", "制度")


def classify_intent(text: str, pending_requirement: bool = False) -> Intent:
    if any(w in text for w in SOLUTION_WORDS):
        return "solution"
    if pending_requirement:
        return "solution"  # 上一轮在追问需求，本轮视为补充信息
    if any(w in text for w in CRM_WORDS):
        return "crm_action"
    return "chitchat"


def llm_intent(deps: AgentDeps, text: str, pending: bool) -> Intent | None:
    """大模型分类；没有模型或调用失败返回 None（由规则兜底）。"""
    if deps.llm is None:
        return None
    hint = "\n（上一轮正在追问方案需求，这句很可能是在补充需求）" if pending else ""
    try:
        classifier = deps.llm.with_structured_output(IntentDecision, method="function_calling")
        out = classifier.invoke([SystemMessage(ROUTER_PROMPT + hint), HumanMessage(text)])
    except Exception:
        logger.warning("router: llm classify failed, fallback to keywords", exc_info=True)
        return None
    return out.intent if isinstance(out, IntentDecision) else None


def make_router(deps: AgentDeps) -> Callable[[AgentState], dict[str, Any]]:
    def router(state: AgentState) -> dict[str, Any]:
        node_start("router")
        pending = bool(state.get("missing"))
        text = state.get("user_message", "")
        if state.get("confirmed_requirement"):
            return {**turn_reset(), "intent": "solution"}  # 需求卡片确认：直接出方案
        if state.get("samples"):
            return {**turn_reset(), "intent": "solution"}  # 上传了客户样例：按样例出方案
        if state.get("material"):
            return {**turn_reset(), "intent": "crm_action"}  # 上传了材料：直接整理写入
        intent = llm_intent(deps, text, pending) or classify_intent(text, pending)
        return {**turn_reset(), "intent": intent}

    return router


def route_intent(state: AgentState) -> str:
    return {"solution": "parse_requirement", "crm_action": "tool_agent"}.get(
        state.get("intent", "chitchat"), "respond"
    )
