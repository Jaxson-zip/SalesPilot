"""出方案链路节点：parse_requirement → [ask_user] → configure → price → check_margin
→（回退 ≤ max_retries 次）→ confirm（interrupt）→ save_quote。

数字（显存、价格、毛利）全部来自工具 / 规则代码，节点只做编排。
需求抽取：有模型时用结构化输出（requirement_fields.extract_with_llm），规则抽取兜底并合并。
"""

import logging
import uuid
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt
from sqlalchemy import select

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
from app.crm.models import Opportunity
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import customer_service, requirement_service
from app.packs.base import MarginHint
from app.packs.registry import get_configurator

Node = Callable[[AgentState], dict[str, Any]]


logger = logging.getLogger(__name__)


def link_customer(deps: AgentDeps, state: AgentState) -> dict[str, Any]:
    """没有从商机进入时，按用户这句话里提到的客户关联报价单。

    只在自己负责的客户里找，且只有唯一匹配才关联（多个或没有都不猜）；
    该客户恰好只有一个进行中的商机时一并关联商机（行业包随商机产品线）。
    """
    if state.get("opportunity_id") or state.get("customer_id"):
        return {}
    try:
        return _match_customer(deps, state)
    except Exception:
        logger.warning("link_customer failed; quote will not be linked", exc_info=True)
        return {}


def _match_customer(deps: AgentDeps, state: AgentState) -> dict[str, Any]:
    with deps.ctx.session() as db:
        found = customer_service.find_mentioned(db, deps.ctx.user, state.get("user_message", ""))
        if len(found) != 1:
            return {}
        customer = found[0]
        opps = db.scalars(
            select(Opportunity.id).where(
                Opportunity.customer_id == customer.id,
                Opportunity.owner_id == deps.ctx.user.id,
                Opportunity.stage.not_in(FINAL_STAGES),
            )
        ).all()
        out: dict[str, Any] = {"customer_id": str(customer.id), "customer_name": customer.name}
        if len(opps) == 1:
            out["opportunity_id"] = str(opps[0])
        return out


def make_parse_requirement(deps: AgentDeps) -> Node:
    def parse_requirement(state: AgentState) -> dict[str, Any]:
        node_start("parse_requirement")
        linked = link_customer(deps, state)
        opp_id = linked.get("opportunity_id", state.get("opportunity_id"))
        try:
            pack_id = deps.resolve_pack(opp_id)
        except BizError as exc:
            return {"error": {"code": exc.code, "message": exc.message}}
        configurator = get_configurator(pack_id)
        saved = load_saved(deps, opp_id, pack_id) if not state.get("requirement") else None
        prev = state.get("requirement") or (saved or {}).get("data") or {}
        prev_confirmed = bool(state.get("requirement_confirmed") or (saved or {}).get("confirmed"))
        if confirmed := state.get("confirmed_requirement"):
            # 需求卡片上确认的结果：不再抽取，直接按它出方案
            args: dict[str, Any] = {"pack_id": pack_id, "text": "", "draft": confirmed}
        else:
            text = state.get("user_message", "")
            hint_fn = getattr(configurator, "extract_hint", None)  # 可选：行业包补充的抽取说明
            hint = hint_fn(prev) if callable(hint_fn) else ""
            args = {
                "pack_id": pack_id,
                "text": text,
                "draft": prev,
                "extracted": extract_with_llm(deps, configurator.requirement_model, text, hint),
            }
        result = call_tool(deps, "parse_requirement", args)
        if not result.ok:
            return {
                "error": tool_error(result),
                "tool_log": log_tool(state, "parse_requirement", result),
            }
        requirement = result.data["requirement"]
        # 确认后只补充预算、工期、交付人数等，仍算已确认；功能或端变了要重新确认
        is_confirmed = bool(confirmed) or (prev_confirmed and same_scope(prev, requirement))
        out = {
            **linked,
            "pack_id": pack_id,
            "requirement": requirement,
            "requirement_confirmed": is_confirmed,
            "missing": result.data["missing"],
            "tool_log": log_tool(state, "parse_requirement", result),
        }
        if confirmed and not out["missing"]:
            save_to_opportunity(deps, {**state, **out})  # type: ignore[typeddict-item]
        return out

    return parse_requirement


def same_scope(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """交付端和功能模块（名称、复杂度、是否首期）是否一致。"""

    def scope(r: dict[str, Any]) -> tuple[list[str], list[tuple[str, str, bool]]]:
        mods = [
            (str(m.get("name")), str(m.get("complexity", "medium")), bool(m.get("must", True)))
            for m in r.get("modules") or []
            if isinstance(m, dict)
        ]
        return sorted(r.get("platforms") or []), sorted(mods)

    return scope(a) == scope(b)


def load_saved(deps: AgentDeps, opp_id: str | None, pack_id: str) -> dict[str, Any] | None:
    """从商机进入时读上次保存的需求清单（同一行业包才用），接着上次的往下走。"""
    if not opp_id:
        return None
    try:
        with deps.ctx.session() as db:
            rec = requirement_service.get_requirement(db, deps.ctx.user, uuid.UUID(opp_id))
    except Exception:
        logger.warning("load saved requirement failed", exc_info=True)
        return None
    return rec.model_dump(mode="json") if rec and rec.pack == pack_id else None


def save_to_opportunity(deps: AgentDeps, state: AgentState, **extra: Any) -> None:
    """把需求清单存到商机上（只有负责人本人能存；失败不影响出方案）。"""
    opp_id = state.get("opportunity_id")
    if not opp_id:
        return
    try:
        with deps.ctx.session() as db:
            requirement_service.save_requirement(
                db,
                deps.ctx.user,
                uuid.UUID(opp_id),
                pack=state.get("pack_id") or "",
                data=state.get("requirement") or {},
                confirmed=bool(state.get("requirement_confirmed")),
                **extra,
            )
    except Exception:
        logger.warning("save requirement failed", exc_info=True)


def route_after_parse(state: AgentState) -> str:
    if state.get("error"):
        return "respond"
    if state.get("missing"):
        return "ask_user"
    configurator = get_configurator(state.get("pack_id") or "")
    if hasattr(configurator, "clarify") and not state.get("requirement_confirmed"):
        return "clarify"
    return "configure"


def make_clarify(deps: AgentDeps) -> Node:
    def clarify(state: AgentState) -> dict[str, Any]:
        """需求还没确认：先给粗估区间和需求卡片，销售和客户核对后再出正式报价。"""
        node_start("clarify")
        configurator = get_configurator(state["pack_id"] or "")
        req = configurator.requirement_model.model_validate(state.get("requirement", {}))
        info: dict[str, Any] = configurator.clarify(req)  # type: ignore[attr-defined]
        card = {
            "pack_id": state.get("pack_id"),
            "opportunity_id": state.get("opportunity_id"),
            "requirement": req.model_dump(mode="json"),
            **info,
        }
        emit("artifact", {"type": "requirement", "data": card})
        save_to_opportunity(
            deps,
            state,
            price_low=info["price_low"],
            price_high=info["price_high"],
            questions=info["questions"],
        )
        text = clarify_text(card)
        emit("message.delta", {"text": text})
        extra = {"artifacts": [{"type": "requirement", "data": card}], "created_at": now_iso()}
        return {
            "clarify": info,
            "messages": [AIMessage(content=text, additional_kwargs=extra)],
        }

    return clarify


def clarify_text(card: dict[str, Any]) -> str:
    """需求卡片上方的说明（模板，数字来自配置器）。"""
    modules = card["requirement"].get("modules") or []
    inferred = card.get("inferred", 0)
    low, high = card["price_low"] / 1_000_000, card["price_high"] / 1_000_000
    head = f"根据描述初步拆出 {len(modules)} 个功能模块"
    if inferred:
        head += f"（其中 {inferred} 个是按业务常识补充的，标了「AI 推断」）"
    lines = [
        f"{head}，粗估 **{low:.1f}–{high:.1f} 万**，可以先给客户这个区间。",
        "",
        *[f"> {n}" for n in card.get("notes") or []],
        *([""] if card.get("notes") else []),
        "正式报价前，建议先和客户确认：",
        *[f"{i}. {q}" for i, q in enumerate(card.get("questions") or [], 1)],
        "",
        "确认后在下面的需求卡片里增删模块、调整复杂度，点「确认需求，出报价」生成三档正式报价。",
    ]
    if card.get("opportunity_id"):
        lines.append("需求清单已保存到商机，下次从商机进入会接着这一版。")
    return "\n".join(lines)


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
        return "explain"
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
            # 从商机进入时客户随商机；否则提示没有识别出客户（这样的报价单不能提交）
            "customer_name": state.get("customer_name")
            or (None if state.get("opportunity_id") else "未识别出客户，报价单只能先存为草稿"),
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
            "customer_id": state.get("customer_id"),
            "idempotency_key": key,
        }
        result = call_tool(deps, "generate_quote", args)
        log = log_tool(state, "generate_quote", result)
        if not result.ok:
            return {"error": tool_error(result), "tool_log": log}
        emit("artifact", {"type": "quote", "data": result.data})
        return {"quote": result.data, "tool_log": log}

    return save_quote
