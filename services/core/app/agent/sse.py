"""把图的执行转成 §8.3 的 SSE 事件。

节点通过 LangGraph custom stream 推送 {event, data}；
interrupt 从 updates 流里的 __interrupt__ 识别；
最后总是推送 done（出错时先推送 error）。图是同步执行的（service 层是同步 SQLAlchemy），
这里在线程池里迭代，避免阻塞事件循环。
"""

import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from starlette.concurrency import iterate_in_threadpool

from app.llm.client import map_llm_error

logger = logging.getLogger("core.agent")
Event = dict[str, Any]


def _interrupt_events(chunk: Any) -> list[Event]:
    if not isinstance(chunk, dict) or "__interrupt__" not in chunk:
        return []
    return [{"event": "interrupt", "data": getattr(i, "value", i)} for i in chunk["__interrupt__"]]


def iter_graph_events(
    graph: CompiledStateGraph, payload: Any, config: RunnableConfig, thread_id: str
) -> Iterator[Event]:
    """同步迭代图的执行，产出 {event, data}。"""
    try:
        for mode, chunk in graph.stream(payload, config, stream_mode=["updates", "custom"]):
            if mode == "custom" and isinstance(chunk, dict) and "event" in chunk:
                yield {"event": chunk["event"], "data": chunk.get("data", {})}
            elif mode == "updates":
                yield from _interrupt_events(chunk)
    except Exception as exc:
        logger.exception("agent run failed thread_id=%s", thread_id)
        err = map_llm_error(exc)
        yield {"event": "error", "data": {"code": err.code, "message": err.message}}
    yield {"event": "done", "data": {"thread_id": thread_id}}


def to_sse(event: Event) -> dict[str, str]:
    """sse-starlette 的消息格式。"""
    return {
        "event": event["event"],
        "data": json.dumps(event["data"], ensure_ascii=False, default=str),
    }


async def sse_stream(
    graph: CompiledStateGraph, payload: Any, config: RunnableConfig, thread_id: str
) -> AsyncIterator[dict[str, str]]:
    async for event in iterate_in_threadpool(iter_graph_events(graph, payload, config, thread_id)):
        yield to_sse(event)
