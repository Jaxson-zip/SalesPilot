"""接口级测试：注入 Fake 后端（代替 litellm），不访问外网。"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fakes import FakeBackend, StreamScript, load_fixture, make_registry, parse_sse

KEY = "test-internal-key"
AUTH = {"Authorization": f"Bearer {KEY}"}
TOOL = {"type": "function", "function": {"name": "search_customers", "parameters": {"type": "object"}}}


def _client(script: dict[str, list[Any]]) -> tuple[TestClient, FakeBackend]:
    backend = FakeBackend(script)
    app = create_app(registry=make_registry(), backend=backend, settings=Settings(gateway_internal_key=KEY))
    return TestClient(app), backend


def _chat(**extra: Any) -> dict[str, Any]:
    return {"model": "g-agent", "messages": [{"role": "user", "content": "查华东客户"}], **extra}


def test_health_without_auth_and_request_id_generated() -> None:
    client, _ = _client({})
    resp = client.get("/health")
    assert resp.status_code == 200 and resp.json()["status"] == "ok"
    assert resp.json()["models"]["m-nokey"]["available"] is False
    assert len(resp.headers["X-Request-ID"]) == 32


def test_missing_or_wrong_key_returns_401_openai_error() -> None:
    client, _ = _client({})
    for headers in ({}, {"Authorization": "Bearer wrong"}):
        resp = client.get("/v1/models", headers={**headers, "X-Request-ID": "rid-1"})
        assert resp.status_code == 401
        assert resp.json()["error"]["gateway_code"] == 40101
        assert resp.headers["X-Request-ID"] == "rid-1"


def test_models_lists_aliases_groups_and_availability() -> None:
    client, _ = _client({})
    data = {m["id"]: m for m in client.get("/v1/models", headers=AUTH).json()["data"]}
    assert data["m-tools"]["available"] is True and data["m-tools"]["capabilities"]["tools"] is True
    assert data["m-nokey"]["available"] is False
    assert data["g-agent"]["type"] == "group"
    assert data["g-agent"]["available_members"] == ["m-plain", "m-tools", "m-pseudo"]


def test_chat_non_stream_normalized_through_compat_layer() -> None:
    client, backend = _client({"m-tools": [load_fixture("hunyuan_tool_call_missing_id.synthetic.json")]})
    resp = client.post(
        "/v1/chat/completions", json=_chat(tools=[TOOL]), headers={**AUTH, "X-Request-ID": "r-9"}
    )
    assert resp.status_code == 200 and resp.headers["X-Request-ID"] == "r-9"
    body = resp.json()
    call = body["choices"][0]["message"]["tool_calls"][0]
    assert call["id"].startswith("call_") and call["type"] == "function"
    assert json.loads(call["function"]["arguments"]) == {"keyword": "华东", "limit": 5}
    assert body["choices"][0]["finish_reason"] == "tool_calls"
    assert body["model"] == "m-tools" and body["usage"]["total_tokens"] == 150
    assert "model" not in backend.calls[0][1]


def test_chat_stream_tool_calls_normalized() -> None:
    chunks = load_fixture("qwen_stream_tool_fragments.synthetic.json")["chunks"]
    client, _ = _client({"m-tools": [StreamScript(chunks)]})
    with client.stream(
        "POST", "/v1/chat/completions", json=_chat(stream=True, tools=[TOOL]), headers=AUTH
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(r.read().decode("utf-8"))
    assert events[-1] == "[DONE]"
    final = events[-2]
    assert final["choices"][0]["finish_reason"] == "tool_calls" and final["usage"]["estimated"] is True
    calls = [
        e["choices"][0]["delta"]["tool_calls"][0]
        for e in events[:-1]
        if "tool_calls" in e["choices"][0]["delta"]
    ]
    assert [c["index"] for c in calls] == [0, 1]
    assert all(c["id"] and c["type"] == "function" for c in calls)
    assert [json.loads(c["function"]["arguments"]) for c in calls] == [
        {"keyword": "华东"},
        {"category": "gpu"},
    ]


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({"model": "g-agent", "messages": []}, 400, 40001),
        ({"model": "nope", "messages": [{"role": "user", "content": "x"}]}, 404, 40401),
        ({"model": "m-plain", "messages": [{"role": "user", "content": "x"}], "tools": [TOOL]}, 400, 40002),
    ],
)
def test_chat_error_codes(payload: dict[str, Any], status: int, code: int) -> None:
    client, _ = _client({})
    resp = client.post("/v1/chat/completions", json=payload, headers=AUTH)
    assert resp.status_code == status
    assert resp.json()["error"]["gateway_code"] == code


def test_stream_all_failed_before_first_byte_returns_http_error() -> None:
    client, _ = _client({"m-tools": [TimeoutError("timed out")], "m-pseudo": [TimeoutError("timed out")]})
    resp = client.post("/v1/chat/completions", json=_chat(stream=True, tools=[TOOL]), headers=AUTH)
    assert resp.status_code == 504
    assert resp.json()["error"]["gateway_code"] == 50401


def test_embeddings_endpoint() -> None:
    client, _ = _client(
        {"m-embed": [{"data": [{"embedding": [0.5], "index": 0}], "usage": {"prompt_tokens": 1}}]}
    )
    resp = client.post("/v1/embeddings", json={"model": "embed", "input": ["a"]}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"][0]["embedding"] == [0.5]


def test_every_request_logs_request_id() -> None:
    """core 只调 /v1/models（没有可用模型时不会发 chat 请求），也要能在网关日志里按 request_id 查到。"""
    import logging

    from app.logging import LOGGER_NAME

    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    try:
        client, _ = _client({})
        client.get("/v1/models", headers={**AUTH, "X-Request-ID": "rid-models"})
        client.get("/health", headers={"X-Request-ID": "rid-health"})
    finally:
        logger.removeHandler(handler)
    logged = [getattr(r, "fields", {}) for r in records if r.getMessage() == "request"]
    assert [f["request_id"] for f in logged] == ["rid-models"]
    assert logged[0]["path"] == "/v1/models" and logged[0]["status"] == 200
