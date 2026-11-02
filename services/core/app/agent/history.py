"""会话历史：从 LangGraph checkpointer 读取状态，还原成前端可直接渲染的消息列表。

- 用户消息 → role=user；AI 最终回复 → role=assistant（工具调用的中间消息不返回）。
- AI 回复的 artifacts / created_at 由 respond 节点写在 AIMessage.additional_kwargs 里；
  早期会话没有这些字段时只返回文字。
- 会话停在 interrupt（等待确认生成报价单）时，追加一条带方案卡片的 assistant 消息，
  并在 pending 里给出待确认的操作。
"""

from datetime import datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.deps import AgentDeps
from app.agent.graph import build_graph
from app.agent.materials import strip as strip_material
from app.agent.nodes.respond import turn_artifacts
from app.agent.runs import registry
from app.agent.threads import ensure_owner, find_thread
from app.agent.tools.base import ToolContext
from app.common.auth import CurrentUser
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode

PENDING_TEXT = "方案已生成，请确认是否生成报价单。"


class Artifact(BaseModel):
    type: str
    data: Any


class MaterialMeta(BaseModel):
    name: str
    chars: int


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    material: MaterialMeta | None = None  # 用户这条消息附带的材料（原文不返回）
    artifacts: list[Artifact] = Field(default_factory=list)
    created_at: datetime | None = None


class ThreadMessages(BaseModel):
    thread_id: str
    messages: list[HistoryMessage]
    pending: dict[str, Any] | None = None  # 待确认操作（interrupt 的 value），没有为 null
    opportunity_id: str | None = None  # 会话关联的商机（从商机出方案或识别出唯一商机）
    mode: Literal["work", "learn"] = "work"  # 会话模式：做方案 / 学习问答
    pack_choice: str | None = None  # 没关联商机时选的行业包（打开历史会话时恢复输入框的选择）
    # 这一轮还在后台生成：messages 是本轮开始前的内容，页面接着订阅 /stream 重放本轮
    running: "RunningInfo | None" = None


class RunningInfo(BaseModel):
    kind: Literal["chat", "resume"]
    input: str  # chat：用户这一轮的消息；resume：approve / reject


def _text(msg: BaseMessage) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
    return "".join(parts)


def to_history(msg: BaseMessage) -> HistoryMessage | None:
    """用户消息与 AI 最终回复；带 tool_calls 或空内容的 AI 中间消息跳过。"""
    extra = msg.additional_kwargs or {}
    created_at = extra.get("created_at")
    if isinstance(msg, HumanMessage):
        material = extra.get("material")
        return HistoryMessage(
            role="user",
            text=strip_material(_text(msg)),
            material=MaterialMeta.model_validate(material) if material else None,
            created_at=created_at,
        )
    if not isinstance(msg, AIMessage) or msg.tool_calls or not _text(msg):
        return None
    arts = [Artifact.model_validate(a) for a in extra.get("artifacts", [])]
    return HistoryMessage(role="assistant", text=_text(msg), artifacts=arts, created_at=created_at)


def _pending(snapshot: StateSnapshot) -> dict[str, Any] | None:
    for task in snapshot.tasks:
        for item in task.interrupts:
            value = getattr(item, "value", None)
            if isinstance(value, dict):
                return value
    return None


def _merge_turns(messages: list[HistoryMessage]) -> list[HistoryMessage]:
    """同一轮里连续的 AI 消息（确认前的方案说明 + 确认后的结果）合成一条，卡片按类型去重。"""
    out: list[HistoryMessage] = []
    for m in messages:
        prev = out[-1] if out else None
        if prev is None or m.role != "assistant" or prev.role != "assistant":
            out.append(m)
            continue
        arts = {a.type: a for a in prev.artifacts} | {a.type: a for a in m.artifacts}
        out[-1] = prev.model_copy(
            update={
                "text": f"{prev.text}\n\n{m.text}",
                "artifacts": list(arts.values()),
                "created_at": m.created_at or prev.created_at,
            }
        )
    return out


def _confirm_card(messages: list[HistoryMessage], requirement: dict[str, Any]) -> None:
    """需求卡确认后：上一张需求卡显示确认时的版本（而不是 AI 最初拆出的草稿），并标为已确认。"""
    for m in reversed(messages):
        for i, a in enumerate(m.artifacts):
            if a.type == "requirement" and isinstance(a.data, dict):
                data = {**a.data, "requirement": requirement, "confirmed": True}
                m.artifacts[i] = Artifact(type=a.type, data=data)
                return


def _history(messages: list[BaseMessage]) -> list[HistoryMessage]:
    out: list[HistoryMessage] = []
    for x in messages:
        confirmed = (x.additional_kwargs or {}).get("requirement")
        if isinstance(x, HumanMessage) and isinstance(confirmed, dict):
            _confirm_card(out, confirmed)
        if (m := to_history(x)) is not None:
            out.append(m)
    return out


def build_messages(thread_id: str, snapshot: StateSnapshot) -> ThreadMessages:
    values: dict[str, Any] = snapshot.values or {}
    raw = _history(values.get("messages", []))
    messages = _merge_turns(raw)
    pending = _pending(snapshot)
    explained = bool(messages) and messages[-1].role == "assistant"
    if pending is not None and not explained:
        arts = [Artifact.model_validate(a) for a in turn_artifacts(values)]
        messages.append(HistoryMessage(role="assistant", text=PENDING_TEXT, artifacts=arts))
    return ThreadMessages(
        thread_id=thread_id,
        messages=messages,
        pending=pending,
        opportunity_id=values.get("opportunity_id"),
        mode="learn" if values.get("mode") == "learn" else "work",
        pack_choice=values.get("pack_choice"),
    )


def _read_only_graph(user: CurrentUser, thread_id: str, saver: BaseCheckpointSaver) -> Any:
    """只用于 get_state：节点不会被执行，不需要模型和数据库。"""
    ctx = ToolContext(user=user, session=session_scope, thread_id=thread_id)
    deps = AgentDeps(ctx=ctx, resolve_pack=lambda _opp: "", llm=None)
    graph: CompiledStateGraph = build_graph(deps, saver)
    return graph


def read_thread_messages(
    db: Session | None, user: CurrentUser, thread_id: str, saver: BaseCheckpointSaver
) -> ThreadMessages:
    """别人的会话 40401（会话表或 checkpoint 任一显示归属他人）；还没有消息的会话返回空列表。"""
    if db is not None:
        ensure_owner(find_thread(db, thread_id), user)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    snapshot = _read_only_graph(user, thread_id, saver).get_state(config)
    owner = (snapshot.values or {}).get("user_id")
    if owner is not None and owner != str(user.id):
        raise BizError(ErrorCode.NOT_FOUND, "会话不存在")
    run = registry.active(thread_id)
    if run is not None and run.user_id == str(user.id) and run.base is not None:
        return run.base.model_copy(update={"running": RunningInfo(kind=run.kind, input=run.input)})
    return build_messages(thread_id, snapshot)
