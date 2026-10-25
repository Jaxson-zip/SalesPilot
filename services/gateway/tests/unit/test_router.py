"""路由：分组失败切换、能力跳过（#12）、首字节前切换 / 中途断开发 error 事件（#14）、伪流式（#11）。"""

from __future__ import annotations

from typing import Any

import pytest

from app.compat.errors import GatewayError
from app.logging import CallLog
from app.router import GatewayRouter
from tests.fakes import FakeBackend, StreamScript, make_registry, parse_sse, text_response, upstream_error

TOOL = {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}


def _body(model: str, **extra: Any) -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "user", "content": "hi"}], **extra}


def _log(model: str) -> CallLog:
    return CallLog("rid", "chat", model)


def _chunk(content: str) -> dict[str, Any]:
    return {"id": "s1", "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}


async def _collect(stream: Any) -> str:
    return "".join([part async for part in stream])


async def test_group_failover_non_stream() -> None:
    backend = FakeBackend({"m-tools": [upstream_error("RateLimitError", 429)], "m-plain": [text_response()]})
    router = GatewayRouter(make_registry(), backend)
    log = _log("g-chat")
    resp = await router.complete(_body("g-chat"), log)
    assert resp["model"] == "m-plain"
    assert log.fallback is True and log.actual_model == "m-plain"
    assert [a["model"] for a in log.attempts] == ["m-tools"]
    assert router.health["m-tools"]["ok"] is False and router.health["m-plain"]["ok"] is True


async def test_group_all_rate_limited_returns_42901() -> None:
    backend = FakeBackend(
        {"m-tools": [upstream_error("RateLimitError", 429)], "m-plain": [upstream_error("X", 429)]}
    )
    with pytest.raises(GatewayError) as info:
        await GatewayRouter(make_registry(), backend).complete(_body("g-chat"), _log("g-chat"))
    assert (info.value.status, info.value.gateway_code) == (429, 42901)


async def test_content_filter_does_not_failover() -> None:
    err = upstream_error("ContentPolicyViolationError", 400, "content_filter")
    backend = FakeBackend({"m-tools": [err], "m-plain": [text_response()]})
    with pytest.raises(GatewayError) as info:
        await GatewayRouter(make_registry(), backend).complete(_body("g-chat"), _log("g-chat"))
    assert info.value.code == "content_filter"
    assert [c[0] for c in backend.calls] == ["m-tools"]


async def test_diff12_group_with_tools_skips_non_tool_model() -> None:
    backend = FakeBackend({"m-tools": [text_response()]})
    router = GatewayRouter(make_registry(), backend)
    await router.complete(_body("g-agent", tools=[TOOL]), _log("g-agent"))
    assert [c[0] for c in backend.calls] == ["m-tools"]  # m-nokey 不可用、m-plain 不支持工具，均被跳过


async def test_diff12_direct_alias_without_tools_returns_40002() -> None:
    router = GatewayRouter(make_registry(), FakeBackend({}))
    with pytest.raises(GatewayError) as info:
        await router.complete(_body("m-plain", tools=[TOOL]), _log("m-plain"))
    assert info.value.gateway_code == 40002


async def test_diff14_failover_before_first_byte() -> None:
    backend = FakeBackend(
        {
            "m-tools": [StreamScript([], error_after=upstream_error("ServiceUnavailableError", 503))],
            "m-plain": [StreamScript([_chunk("ok")])],
        }
    )
    log = _log("g-chat")
    stream = await GatewayRouter(make_registry(), backend).open_stream(_body("g-chat", stream=True), log)
    events = parse_sse(await _collect(stream))
    assert events[-1] == "[DONE]"
    assert events[-2]["choices"][0]["finish_reason"] == "stop" and "usage" in events[-2]
    assert log.actual_model == "m-plain" and log.fallback is True
    assert backend.calls[1][1]["stream_options"] == {"include_usage": True}


async def test_diff14_mid_stream_failure_sends_error_event_without_failover() -> None:
    backend = FakeBackend(
        {
            "m-tools": [
                StreamScript(
                    [_chunk("部分"), _chunk("输出")], error_after=upstream_error("APIConnectionError", None)
                )
            ],
            "m-plain": [StreamScript([_chunk("不应该被调用")])],
        }
    )
    log = _log("g-chat")
    stream = await GatewayRouter(make_registry(), backend).open_stream(_body("g-chat", stream=True), log)
    events = parse_sse(await _collect(stream))
    assert events[-1]["error"]["gateway_code"] == 50201
    assert "[DONE]" not in events
    assert [c[0] for c in backend.calls] == ["m-tools"]
    assert log.status == "error"


async def test_diff11_pseudo_stream_when_model_cannot_stream_tools() -> None:
    upstream = {
        "choices": [{"message": {"tool_calls": [{"function": {"name": "lookup", "arguments": "{}"}}]}}]
    }
    backend = FakeBackend({"m-pseudo": [upstream]})
    log = _log("m-pseudo")
    stream = await GatewayRouter(make_registry(), backend).open_stream(
        _body("m-pseudo", stream=True, tools=[TOOL]), log
    )
    events = parse_sse(await _collect(stream))
    assert backend.calls[0][1]["stream"] is False
    assert log.pseudo_stream is True
    call = events[1]["choices"][0]["delta"]["tool_calls"][0]
    assert call["id"].startswith("call_") and call["type"] == "function"
    assert events[-2]["choices"][0]["finish_reason"] == "tool_calls"


async def test_embeddings_routed_to_embed_group() -> None:
    backend = FakeBackend({"m-embed": [{"data": [{"embedding": [0.1, 0.2], "index": 0}], "usage": {}}]})
    resp = await GatewayRouter(make_registry(), backend).embed(
        {"model": "embed", "input": "hi"}, _log("embed")
    )
    assert resp["model"] == "m-embed" and resp["data"][0]["embedding"] == [0.1, 0.2]
    assert backend.calls[0][1] == {"input": "hi"}
