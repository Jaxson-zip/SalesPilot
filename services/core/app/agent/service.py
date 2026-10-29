"""Agent 会话编排：构造依赖、校验会话归属、准备 chat / resume 的图输入。"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.agent import samples as sample_lib
from app.agent.checkpoint import get_checkpointer
from app.agent.deps import AgentDeps
from app.agent.graph import build_graph
from app.agent.history import build_messages
from app.agent.materials import MaterialIn, compose
from app.agent.nodes import solution
from app.agent.nodes.common import now_iso
from app.agent.runs import Run, RunKind, registry
from app.agent.sse import iter_graph_events
from app.agent.state import Mode
from app.agent.threads import touch_thread
from app.agent.tools.base import ToolContext
from app.common.auth import CurrentUser
from app.common.config import get_settings
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.crm.services import opportunity_service
from app.llm.client import get_chat_model, model_available
from app.rules import load_rules

logger = logging.getLogger("core.agent")


@dataclass
class PreparedRun:
    graph: CompiledStateGraph
    payload: Any
    config: RunnableConfig
    thread_id: str
    kind: RunKind = "chat"
    input: str = ""
    base: Any = None  # 这一轮开始前的会话（ThreadMessages）


def make_pack_resolver(user: CurrentUser) -> Any:
    default_pack = get_settings().default_pack

    def resolve(opportunity_id: str | None) -> str:
        opp = uuid.UUID(opportunity_id) if opportunity_id else None
        try:
            with session_scope() as db:
                return opportunity_service.resolve_pack(db, user, opp, default_pack)
        except BizError:
            raise
        except Exception as exc:
            if opp is not None:
                raise BizError(ErrorCode.INTERNAL, "读取商机失败") from exc
            logger.warning("resolve_pack: db unavailable, use default pack %s", default_pack)
            return default_pack

    return resolve


def build_deps(user: CurrentUser, thread_id: str, request_id: str, model: str | None) -> AgentDeps:
    rules = load_rules()
    ctx = ToolContext(
        user=user,
        session=session_scope,
        thread_id=thread_id,
        request_id=request_id,
        default_pack=get_settings().default_pack,
    )
    return AgentDeps(
        ctx=ctx,
        resolve_pack=make_pack_resolver(user),
        # 网关里没有可用模型（未配置 Key）时不创建客户端，各节点走规则 / 模板兜底
        llm=get_chat_model(model, request_id=request_id)
        if model_available(model, request_id)
        else None,
        max_retries=rules.agent.margin_max_retries,
        max_tool_calls=rules.agent.max_tool_calls,
    )


def _config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


def _check_owner(graph: CompiledStateGraph, config: RunnableConfig, user: CurrentUser) -> Any:
    snapshot = graph.get_state(config)
    owner = (snapshot.values or {}).get("user_id")
    if owner is not None and owner != str(user.id):
        raise BizError(ErrorCode.NOT_FOUND, "会话不存在")
    return snapshot


def prepare_chat(
    deps: AgentDeps,
    message: str,
    opportunity_id: uuid.UUID | None,
    material: MaterialIn | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    requirement: dict[str, Any] | None = None,
    samples: sample_lib.SamplesIn | None = None,
    mode: Mode = "work",
) -> PreparedRun:
    thread_id = deps.ctx.thread_id
    graph = build_graph(deps, checkpointer or get_checkpointer())
    config = _config(thread_id)
    snapshot = _check_owner(graph, config, deps.ctx.user)
    _ensure_idle(thread_id)
    existing = snapshot.values or {}
    if existing.get("user_id"):
        # 模式在会话第一轮确定，之后沿用：学习问答的会话不会被切到能写数据的模式
        mode = "learn" if existing.get("mode") == "learn" else "work"
    extra: dict[str, Any] = {"created_at": now_iso()}
    content = message
    if material is not None:
        extra["material"] = {"name": material.name, "chars": len(material.text)}
        content = compose(message, material)
    summary = sample_lib.summarize(samples) if samples else None
    if summary is not None:
        extra["material"] = {"name": sample_lib.label(summary), "chars": 0}  # 名称已含张数
        content = sample_lib.compose(message, summary)
    payload: dict[str, Any] = {
        "messages": [HumanMessage(content=content, additional_kwargs=extra)],
        "user_id": str(deps.ctx.user.id),
        "user_message": message,
        "material": material.name if material else None,
        "confirmed_requirement": requirement,
        "samples": summary.model_dump() if summary else None,
        "mode": mode,
    }
    # 没带商机（例如从历史记录重新打开的会话）时不覆盖：会话之前关联的商机继续有效
    if opportunity_id:
        payload["opportunity_id"] = str(opportunity_id)
    touch_thread(deps.ctx.session, deps.ctx.user, thread_id, message, opportunity_id, mode)
    return PreparedRun(
        graph, payload, config, thread_id, "chat", message, build_messages(thread_id, snapshot)
    )


def prepare_resume(
    deps: AgentDeps,
    decision: str,
    checkpointer: BaseCheckpointSaver | None = None,
    tier: str | None = None,
    items: dict[str, int] | None = None,
) -> PreparedRun:
    thread_id = deps.ctx.thread_id
    graph = build_graph(deps, checkpointer or get_checkpointer())
    config = _config(thread_id)
    snapshot = _check_owner(graph, config, deps.ctx.user)
    if not snapshot.values or not snapshot.next:
        raise BizError(ErrorCode.NOT_FOUND, "没有待确认的操作")
    _ensure_idle(thread_id)
    base = build_messages(thread_id, snapshot)
    value: str | dict[str, Any] = decision
    if (tier or items) and decision == "approve":
        value = _quote_choice(snapshot, tier, items)
    return PreparedRun(graph, Command(resume=value), config, thread_id, "resume", decision, base)


def _quote_choice(snapshot: Any, tier: str | None, items: dict[str, int] | None) -> dict[str, Any]:
    """生成报价单时另选的档位、调整的数量：先校验（不合法直接报错，不进入图）。"""
    tiers = snapshot.values.get("tiers") or []
    if _pending_action(snapshot) != "generate_quote":
        raise BizError(ErrorCode.VALIDATION, "当前没有待确认的报价单")
    if tier and tier not in {t.get("tier") for t in tiers}:
        raise BizError(ErrorCode.VALIDATION, "没有这个方案档位，请在方案卡片里重新选择")
    if items:
        picked = solution.chosen_tier({**snapshot.values, "chosen_tier": tier})
        try:
            solution.adjusted(snapshot.values["pack_id"], picked, items)
        except ValueError as e:
            raise BizError(ErrorCode.VALIDATION, str(e)) from e
    return {"decision": "approve", "tier": tier, "items": items or None}


def _pending_action(snapshot: Any) -> str | None:
    """当前等待确认的写操作（interrupt 的 action）。"""
    for task in snapshot.tasks or ():
        for it in task.interrupts or ():
            if isinstance(it.value, dict):
                return it.value.get("action")
    return None


def _ensure_idle(thread_id: str) -> None:
    if registry.active(thread_id) is not None:
        raise BizError(ErrorCode.DUPLICATE, "上一条回复还在生成，请等它完成或先停止")


def start_run(run: PreparedRun, user: CurrentUser) -> Run:
    """在后台跑完这一轮（浏览器断开也不中断），返回可订阅的 Run。"""
    events = iter_graph_events(run.graph, run.payload, run.config, run.thread_id)
    info = Run(
        thread_id=run.thread_id, user_id=str(user.id), kind=run.kind, input=run.input, base=run.base
    )
    return registry.start(info, events)
