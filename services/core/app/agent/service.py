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

from app.agent.checkpoint import get_checkpointer
from app.agent.deps import AgentDeps
from app.agent.graph import build_graph
from app.agent.nodes.common import now_iso
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
    checkpointer: BaseCheckpointSaver | None = None,
) -> PreparedRun:
    thread_id = deps.ctx.thread_id
    graph = build_graph(deps, checkpointer or get_checkpointer())
    config = _config(thread_id)
    _check_owner(graph, config, deps.ctx.user)
    payload = {
        "messages": [HumanMessage(content=message, additional_kwargs={"created_at": now_iso()})],
        "user_id": str(deps.ctx.user.id),
        "user_message": message,
        "opportunity_id": str(opportunity_id) if opportunity_id else None,
    }
    touch_thread(deps.ctx.session, deps.ctx.user, thread_id, message, opportunity_id)
    return PreparedRun(graph, payload, config, thread_id)


def prepare_resume(
    deps: AgentDeps, decision: str, checkpointer: BaseCheckpointSaver | None = None
) -> PreparedRun:
    thread_id = deps.ctx.thread_id
    graph = build_graph(deps, checkpointer or get_checkpointer())
    config = _config(thread_id)
    snapshot = _check_owner(graph, config, deps.ctx.user)
    if not snapshot.values or not snapshot.next:
        raise BizError(ErrorCode.NOT_FOUND, "没有待确认的操作")
    return PreparedRun(graph, Command(resume=decision), config, thread_id)
