"""请求规范化：差异 #1–#4。"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.compat.errors import GatewayError
from app.compat.request import (
    JSON_HINT,
    REQUIRED_TOOL_HINT,
    normalize_request,
    simplify_schema,
    wants_json,
)
from app.registry import Capabilities

TOOL = {
    "type": "function",
    "function": {
        "name": "search_customers",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                "limit": {"type": "integer", "default": 10, "title": "Limit"},
            },
        },
    },
}


def _body(**extra: Any) -> dict[str, Any]:
    return {"model": "x", "messages": [{"role": "user", "content": "hi"}], **extra}


# ---------- #1 参数不被支持 ----------


def test_diff01_tool_choice_required_downgraded_with_hint() -> None:
    req, notes = normalize_request(_body(tools=[TOOL], tool_choice="required"), Capabilities(tools=True))
    assert req["tool_choice"] == "auto"
    assert req["messages"][0] == {"role": "system", "content": REQUIRED_TOOL_HINT}
    assert "tool_choice:required->auto" in notes


def test_diff01_tool_choice_required_kept_when_supported() -> None:
    caps = Capabilities(tools=True, tool_choice_required=True)
    req, notes = normalize_request(_body(tools=[TOOL], tool_choice="required"), caps)
    assert req["tool_choice"] == "required"
    assert notes == []


def test_diff01_parallel_tool_calls_and_seed_dropped() -> None:
    req, notes = normalize_request(_body(parallel_tool_calls=True, seed=7), Capabilities())
    assert "parallel_tool_calls" not in req and "seed" not in req
    assert {"parallel_tool_calls:dropped", "seed:dropped"} <= set(notes)


def test_diff01_json_schema_to_json_object() -> None:
    fmt = {"type": "json_schema", "json_schema": {"name": "q", "schema": {"type": "object"}}}
    req, notes = normalize_request(_body(response_format=fmt), Capabilities(json_mode=True))
    assert req["response_format"] == {"type": "json_object"}
    assert JSON_HINT in req["messages"][0]["content"]
    assert "JSON Schema" in req["messages"][0]["content"]
    assert "response_format:json_schema->json_object" in notes


def test_diff01_json_object_to_prompt_when_no_json_mode() -> None:
    body = _body(response_format={"type": "json_object"})
    req, notes = normalize_request(body, Capabilities(json_mode=False))
    assert "response_format" not in req
    assert req["messages"][0]["role"] == "system"
    assert "response_format:json_object->prompt" in notes
    assert wants_json(body)


# ---------- #2 参数命名和范围 ----------


def test_diff02_max_completion_tokens_mapped() -> None:
    req, notes = normalize_request(_body(max_completion_tokens=256), Capabilities())
    assert req["max_tokens"] == 256 and "max_completion_tokens" not in req
    assert "max_completion_tokens->max_tokens" in notes


def test_diff02_reverse_mapping_and_output_clamp() -> None:
    caps = Capabilities(max_tokens_param="max_completion_tokens", max_output_tokens=100)
    req, _ = normalize_request(_body(max_tokens=4000), caps)
    assert req["max_completion_tokens"] == 100
    assert "max_tokens" not in req


@pytest.mark.parametrize(("value", "expected"), [(1.8, 1.0), (-0.5, 0.0), (0.7, 0.7)])
def test_diff02_temperature_clamped(value: float, expected: float) -> None:
    req, _ = normalize_request(_body(temperature=value), Capabilities(temperature_max=1.0))
    assert req["temperature"] == expected


# ---------- #3 消息格式 ----------


def test_diff03_system_messages_merged_to_front() -> None:
    msgs = [
        {"role": "user", "content": "q1"},
        {"role": "system", "content": "A"},
        {"role": "system", "content": [{"type": "text", "text": "B"}]},
    ]
    req, notes = normalize_request({"model": "x", "messages": msgs}, Capabilities())
    assert req["messages"][0] == {"role": "system", "content": "A\n\nB"}
    assert [m["role"] for m in req["messages"]] == ["system", "user"]
    assert "messages:system_merged" in notes


def test_diff03_null_content_and_parts_flattened() -> None:
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "看"}, {"type": "text", "text": "图"}]},
        {"role": "assistant", "content": None},
    ]
    req, _ = normalize_request({"model": "x", "messages": msgs}, Capabilities())
    assert req["messages"][0]["content"] == "看图"
    assert req["messages"][1]["content"] == ""


def test_diff03_tool_results_reordered_and_missing_filled() -> None:
    calls = [
        {"id": "c1", "type": "function", "function": {"name": "a", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {"name": "b", "arguments": "{}"}},
    ]
    msgs = [
        {"role": "user", "content": "q"},
        {"role": "tool", "tool_call_id": "c1", "content": "r1"},
        {"role": "assistant", "content": None, "tool_calls": calls},
        {"role": "user", "content": "继续"},
    ]
    req, notes = normalize_request({"model": "x", "messages": msgs}, Capabilities())
    roles = [(m["role"], m.get("tool_call_id")) for m in req["messages"]]
    assert roles == [("user", None), ("assistant", None), ("tool", "c1"), ("tool", "c2"), ("user", None)]
    assert "messages:tool_results_reordered" in notes
    assert "messages:missing_tool_result_filled" in notes


def test_diff03_orphan_tool_message_rejected() -> None:
    msgs = [{"role": "user", "content": "q"}, {"role": "tool", "tool_call_id": "nope", "content": "r"}]
    with pytest.raises(GatewayError) as info:
        normalize_request({"model": "x", "messages": msgs}, Capabilities())
    assert info.value.gateway_code == 40001


# ---------- #4 工具定义 ----------


@pytest.mark.parametrize("name", ["查询客户", "a" * 65, "bad name", ""])
def test_diff04_invalid_tool_name_rejected(name: str) -> None:
    tool = {"type": "function", "function": {"name": name, "parameters": {}}}
    with pytest.raises(GatewayError) as info:
        normalize_request(_body(tools=[tool]), Capabilities(tools=True))
    assert info.value.gateway_code == 40001 and info.value.param == "tools"


def test_diff04_schema_simplified_when_required() -> None:
    req, notes = normalize_request(_body(tools=[TOOL]), Capabilities(tools=True, simple_schema=True))
    props = req["tools"][0]["function"]["parameters"]["properties"]
    assert props["keyword"] == {"type": "string"}
    assert props["limit"] == {"type": "integer"}
    assert "tools:schema_simplified" in notes


def test_diff04_schema_kept_when_supported_and_input_not_mutated() -> None:
    body = _body(tools=[TOOL])
    snapshot = copy.deepcopy(body)
    req, _ = normalize_request(body, Capabilities(tools=True))
    assert req["tools"][0]["function"]["parameters"] == TOOL["function"]["parameters"]
    assert body == snapshot


def test_simplify_schema_handles_nested_and_oneof() -> None:
    schema = {
        "type": "array",
        "items": {
            "oneOf": [
                {"type": "null"},
                {"type": "object", "properties": {"default": {"type": "string", "default": "x"}}},
            ]
        },
    }
    assert simplify_schema(schema) == {
        "type": "array",
        "items": {"type": "object", "properties": {"default": {"type": "string"}}},
    }
