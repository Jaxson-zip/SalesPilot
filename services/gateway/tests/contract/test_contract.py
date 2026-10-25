"""契约测试：每个模型别名跑 10 个用例（开发规范 §12.1）。访问真实模型，默认 skip。

RUN_CONTRACT=1 uv run pytest tests/contract -k deepseek-chat
uv run python scripts/compat_matrix.py      # 根据 results.json 更新 docs/模型兼容矩阵.md
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.backend import LiteLLMBackend
from app.config import Settings
from app.main import create_app
from app.registry import Registry
from tests.contract.support import CONTRACT_ENABLED, RecordingBackend, chat_aliases, project_registry
from tests.fakes import parse_sse

pytestmark = pytest.mark.contract

KEY = "contract-key"
AUTH = {"Authorization": f"Bearer {KEY}"}
WEATHER = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询城市天气",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    },
}
CASES = [
    "chat",
    "chat_stream",
    "tool_single",
    "tool_parallel",
    "tool_stream",
    "tool_second_turn",
    "json_output",
    "context_overflow",
    "bad_key",
    "group_failover",
]


def _client(registry: Registry, case: str) -> TestClient:
    backend = RecordingBackend(LiteLLMBackend(registry, registry.settings.timeout_seconds), case)
    app = create_app(registry=registry, backend=backend, settings=Settings(gateway_internal_key=KEY))
    return TestClient(app)


def _post(client: TestClient, alias: str, **body: Any) -> Any:
    return client.post("/v1/chat/completions", json={"model": alias, **body}, headers=AUTH)


def _user(text: str) -> list[dict[str, Any]]:
    return [{"role": "user", "content": text}]


def _tool_calls(resp: Any) -> list[dict[str, Any]]:
    assert resp.status_code == 200, resp.text
    calls = resp.json()["choices"][0]["message"].get("tool_calls") or []
    for call in calls:
        assert call["id"] and call["type"] == "function"
        json.loads(call["function"]["arguments"])
    return calls


def _stream(client: TestClient, alias: str, **body: Any) -> list[Any]:
    with client.stream(
        "POST", "/v1/chat/completions", json={"model": alias, "stream": True, **body}, headers=AUTH
    ) as r:
        assert r.status_code == 200
        events = parse_sse(r.read().decode("utf-8"))
    assert events[-1] == "[DONE]", events[-1]
    assert events[-2]["choices"][0]["finish_reason"] and "usage" in events[-2]
    return events


def case_chat(reg: Registry, alias: str) -> None:
    resp = _post(_client(reg, "chat"), alias, messages=_user("只回复两个字：你好"))
    assert resp.status_code == 200 and resp.json()["choices"][0]["message"]["content"]


def case_chat_stream(reg: Registry, alias: str) -> None:
    events = _stream(_client(reg, "chat_stream"), alias, messages=_user("用一句话介绍你自己"))
    assert events[-2]["choices"][0]["finish_reason"] == "stop"


def case_tool_single(reg: Registry, alias: str) -> None:
    resp = _post(_client(reg, "tool_single"), alias, messages=_user("北京天气怎么样？"), tools=[WEATHER])
    assert len(_tool_calls(resp)) >= 1


def case_tool_parallel(reg: Registry, alias: str) -> None:
    resp = _post(
        _client(reg, "tool_parallel"), alias, messages=_user("同时查询北京和上海的天气"), tools=[WEATHER]
    )
    assert len(_tool_calls(resp)) >= 2


def case_tool_stream(reg: Registry, alias: str) -> None:
    events = _stream(_client(reg, "tool_stream"), alias, messages=_user("北京天气怎么样？"), tools=[WEATHER])
    calls = [
        e["choices"][0]["delta"]["tool_calls"][0]
        for e in events[:-1]
        if e["choices"][0]["delta"].get("tool_calls")
    ]
    assert calls and all(c["id"] for c in calls)
    assert events[-2]["choices"][0]["finish_reason"] == "tool_calls"


def case_tool_second_turn(reg: Registry, alias: str) -> None:
    call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_weather", "arguments": '{"city": "北京"}'},
    }
    messages = [
        *_user("北京天气怎么样？"),
        {"role": "assistant", "content": None, "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"weather": "晴", "temp": 20}'},
    ]
    resp = _post(_client(reg, "tool_second_turn"), alias, messages=messages, tools=[WEATHER])
    assert resp.status_code == 200 and "晴" in resp.json()["choices"][0]["message"]["content"]


def case_json_output(reg: Registry, alias: str) -> None:
    resp = _post(
        _client(reg, "json_output"),
        alias,
        messages=_user('输出 JSON：{"ok": true}'),
        response_format={"type": "json_object"},
    )
    assert resp.status_code == 200
    json.loads(resp.json()["choices"][0]["message"]["content"])


def case_context_overflow(reg: Registry, alias: str) -> None:
    size = (reg.models[alias].capabilities.max_context or 128000) * 2
    resp = _post(_client(reg, "context_overflow"), alias, messages=_user("字" * size))
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "context_length_exceeded"


def _with_bad_copy(reg: Registry, alias: str) -> Registry:
    bad = reg.models[alias].model_copy(update={"alias": f"{alias}-badkey", "api_key": "sk-invalid-for-test"})
    models = {**reg.models, bad.alias: bad}
    groups = {**reg.groups, "contract-failover": [bad.alias, alias]}
    return Registry(models=models, groups=groups, settings=reg.settings.model_copy(update={"retries": 0}))


def case_bad_key(reg: Registry, alias: str) -> None:
    resp = _post(_client(_with_bad_copy(reg, alias), "bad_key"), f"{alias}-badkey", messages=_user("hi"))
    assert resp.status_code == 401 and resp.json()["error"]["gateway_code"] == 40101


def case_group_failover(reg: Registry, alias: str) -> None:
    resp = _post(
        _client(_with_bad_copy(reg, alias), "group_failover"), "contract-failover", messages=_user("hi")
    )
    assert resp.status_code == 200 and resp.json()["model"] == alias


CASE_FUNCS: dict[str, Callable[[Registry, str], None]] = {name: globals()[f"case_{name}"] for name in CASES}
PARAMS = [(alias, case) for alias in chat_aliases() for case in CASES]


@pytest.mark.parametrize(("alias", "case"), PARAMS, ids=[f"{a}-case_{c}" for a, c in PARAMS])
def test_contract(alias: str, case: str) -> None:
    if not CONTRACT_ENABLED:
        pytest.skip("set RUN_CONTRACT=1 to run contract tests against real models")
    reg = project_registry()
    if not reg.models[alias].available:
        pytest.skip(f"{alias}: {reg.models[alias].unavailable_reason}")
    CASE_FUNCS[case](reg, alias)
