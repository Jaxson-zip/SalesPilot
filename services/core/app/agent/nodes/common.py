"""节点公共工具：事件推送（LangGraph custom stream）与工具调用。"""

from datetime import UTC, datetime
from typing import Any

from langgraph.config import get_stream_writer

from app.agent.deps import AgentDeps
from app.agent.state import AgentState
from app.agent.tools import TOOLS, ToolResult, run_tool


def emit(event: str, data: dict[str, Any]) -> None:
    """推送一条 SSE 事件（§8.3）；不在图里运行时静默忽略。"""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer({"event": event, "data": data})


def now_iso() -> str:
    """消息时间戳（存进 message.additional_kwargs，会话历史用）。"""
    return datetime.now(UTC).isoformat()


def node_start(name: str) -> None:
    emit("node.start", {"node": name})


def call_tool(deps: AgentDeps, name: str, args: dict[str, Any]) -> ToolResult:
    return run_tool(TOOLS[name], deps.ctx, args, emit)


def log_tool(state: AgentState, name: str, result: ToolResult) -> list[dict[str, Any]]:
    """把工具结果摘要追加到本轮日志，respond 节点据此生成回复。"""
    entry = {"tool": name, "ok": result.ok, "summary": result.summary}
    return [*state.get("tool_log", []), entry]


def tool_error(result: ToolResult) -> dict[str, Any]:
    return result.error or {"code": 50001, "message": result.summary}
