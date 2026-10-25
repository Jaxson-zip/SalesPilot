"""真实 LiteLLMBackend + litellm 的 mock_response（不访问外网），验证 Router 构造和流式整理链路。"""

from __future__ import annotations

from typing import Any

from app.backend import LiteLLMBackend, build_model_list
from app.logging import CallLog
from app.router import GatewayRouter
from tests.fakes import make_registry, parse_sse


def test_model_list_only_contains_available_models() -> None:
    names = [m["model_name"] for m in build_model_list(make_registry(), 5)]
    assert "m-nokey" not in names and "m-tools" in names
    params = build_model_list(make_registry(), 5)[0]["litellm_params"]
    assert params["model"] == "openai/x" and params["api_base"] == "http://upstream.invalid/v1"


async def test_litellm_mock_response_through_router() -> None:
    registry = make_registry()
    router = GatewayRouter(registry, LiteLLMBackend(registry, 5))
    body: dict[str, Any] = {
        "model": "g-chat",
        "messages": [{"role": "user", "content": "hi"}],
        "mock_response": "hello world",
    }
    resp = await router.complete(body, CallLog("r", "chat", "g-chat"))
    assert resp["choices"][0]["message"] == {"role": "assistant", "content": "hello world"}
    stream = await router.open_stream({**body, "stream": True}, CallLog("r", "chat", "g-chat", stream=True))
    events = parse_sse("".join([part async for part in stream]))
    text = "".join(e["choices"][0]["delta"].get("content", "") for e in events[:-1])
    assert text == "hello world"
    assert events[-2]["choices"][0]["finish_reason"] == "stop" and "usage" in events[-2]
