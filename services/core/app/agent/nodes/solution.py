"""出方案链路节点：parse_requirement → [ask_user] → configure → price → check_margin
→（回退 ≤ max_retries 次）→ confirm（interrupt）→ save_quote。

数字（显存、价格、毛利）全部来自工具 / 规则代码，节点只做编排。
需求抽取：有模型时用结构化输出（requirement_fields.extract_with_llm），规则抽取兜底并合并。
"""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agent.deps import AgentDeps
from app.agent.nodes.common import (
    call_tool,
    emit,
    log_tool,
    node_start,
    now_iso,
    tool_error,
)
from app.agent.nodes.requirement_fields import extract_with_llm
from app.agent.state import AgentState
from app.common.errors import BizError
from app.packs.base import MarginHint
from app.packs.registry import get_configurator

Node = Callable[[AgentState], dict[str, Any]]


def make_parse_requirement(deps: AgentDeps) -> Node:
    def parse_requirement(state: AgentState) -> dict[str, Any]:
        node_start("parse_requirement")
        try:
            pack_id = deps.resolve_pack(state.get("opportunity_id"))
        except BizError as exc:
            return {"error": {"code": exc.code, "message": exc.message}}
        text = state.get("user_message", "")
        model = get_configurator(pack_id).requirement_model
        args = {
            "pack_id": pack_id,
            "text": text,
            "draft": state.get("requirement", {}),
            "extracted": extract_with_llm(deps, model, text),
        }
        result = call_tool(deps, "parse_requirement", args)
        if not result.ok:
            return {
                "error": tool_error(result),
                "tool_log": log_tool(state, "parse_requirement", result),
            }
        return {
            "pack_id": pack_id,
            "requirement": result.data["requirement"],
            "missing": result.data["missing"],
            "tool_log": log_tool(state, "parse_requirement", result),
        }

    return parse_requirement


def route_after_parse(state: AgentState) -> str:
    if state.get("error"):
        return "respond"
    return "ask_user" if state.get("missing") else "configure"


def make_ask_user(deps: AgentDeps) -> Node:
    def ask_user(state: AgentState) -> dict[str, Any]:
        node_start("ask_user")
        model = get_configurator(state["pack_id"] or "").requirement_model
        labels = [
            model.model_fields[f].description or f if f in model.model_fields else f
            for f in state.get("missing", [])
        ]
        text = f"为了给出准确的配置和报价，还需要确认：{'；'.join(labels)}。"
        emit("message.delta", {"text": text})
        return {"messages": [AIMessage(content=text, additional_kwargs={"created_at": now_iso()})]}

    return ask_user


def make_configure(deps: AgentDeps) -> Node:
    def configure(state: AgentState) -> dict[str, Any]:
        node_start("configure")
        args = {
            "pack_id": state["pack_id"],
            "requirement": state.get("requirement", {}),
            "hint": state.get("hint"),
        }
        result = call_tool(deps, "configure_solution", args)
        if not result.ok:
            return {
                "error": tool_error(result),
                "tool_log": log_tool(state, "configure_solution", result),
            }
        return {"tiers": result.data, "tool_log": log_tool(state, "configure_solution", result)}

    return configure


def route_after_configure(state: AgentState) -> str:
    return "respond" if state.get("error") else "price"


def recommended_tier(tiers: list[dict[str, Any]]) -> dict[str, Any]:
    return next((t for t in tiers if t.get("recommended")), tiers[0])


def make_price(deps: AgentDeps) -> Node:
    def price(state: AgentState) -> dict[str, Any]:
        """价格已由行业包配置器按目录和规则算好；这里推送方案卡片和推荐档位的物料清单。"""
        node_start("price")
        tiers = state.get("tiers", [])
        emit("artifact", {"type": "solution_tiers", "data": tiers})
        if tiers:
            emit("artifact", {"type": "bom", "data": recommended_tier(tiers)})
        return {}

    return price


def make_check_margin(deps: AgentDeps) -> Node:
    def check_margin(state: AgentState) -> dict[str, Any]:
        node_start("check_margin")
        tiers = state.get("tiers", [])
        prices = [
            {"tier": t["tier"], "total_cost": t["total_cost"], "total_price": t["total_price"]}
            for t in tiers
        ]
        args = {"pack_id": state["pack_id"], "tiers": prices}
        result = call_tool(deps, "check_margin", args)
        log = log_tool(state, "check_margin", result)
        if not result.ok:
            return {"error": tool_error(result), "tool_log": log}
        if result.data["passed"]:
            return {"margin_ok": True, "margin_reason": result.summary, "tool_log": log}
        retry = state.get("retry", 0)
        # hint 为 None 表示不再回退，交给销售决定
        update: dict[str, Any] = {"margin_ok": False, "margin_reason": result.summary, "hint": None}
        if retry < deps.max_retries:
            low = [r["tier"] for r in result.data["results"] if not r["passed"]]
            hint = MarginHint(attempt=retry + 1, low_tiers=low)
            emit(
                "node.retry", {"node": "configure", "reason": result.summary, "attempt": retry + 1}
            )
            update.update({"retry": retry + 1, "hint": hint.dump()})
        return {**update, "tool_log": log}

    return check_margin


def route_after_margin(state: AgentState) -> str:
    if state.get("error"):
        return "respond"
    if state.get("margin_ok"):
        return "confirm"
    return "configure" if state.get("hint") else "respond"


def make_confirm(deps: AgentDeps) -> Node:
    def confirm(state: AgentState) -> dict[str, Any]:
        """写操作前中断，等用户确认。

        注意：resume 时本节点会重新执行，interrupt 之前不能有副作用。
        """
        tier = recommended_tier(state.get("tiers", []))
        preview = {
            "pack_id": state.get("pack_id"),
            "opportunity_id": state.get("opportunity_id"),
            "tier": tier.get("tier"),
            "name": tier.get("name"),
            "summary": tier.get("summary"),
            "total_price": tier.get("total_price"),
            "margin_rate": tier.get("margin_rate"),
        }
        decision = interrupt({"action": "generate_quote", "preview": preview})
        return {"decision": str(decision)}

    return confirm


def route_after_confirm(state: AgentState) -> str:
    return "save_quote" if state.get("decision") == "approve" else "respond"


def make_save_quote(deps: AgentDeps) -> Node:
    def save_quote(state: AgentState) -> dict[str, Any]:
        node_start("save_quote")
        tier = recommended_tier(state.get("tiers", []))
        key = f"agent:{deps.ctx.thread_id}:{tier['tier']}:{tier['total_price']}"
        args = {
            "pack_id": state["pack_id"],
            "tier": tier,
            "opportunity_id": state.get("opportunity_id"),
            "idempotency_key": key,
        }
        result = call_tool(deps, "generate_quote", args)
        log = log_tool(state, "generate_quote", result)
        if not result.ok:
            return {"error": tool_error(result), "tool_log": log}
        emit("artifact", {"type": "quote", "data": result.data})
        return {"quote": result.data, "tool_log": log}

    return save_quote
