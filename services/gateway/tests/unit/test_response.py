"""响应规范化：差异 #5 #6 #8 #9。"""

from __future__ import annotations

import json

import pytest

from app.compat.errors import GatewayError
from app.compat.response import (
    ensure_json_content,
    map_finish_reason,
    normalize_embedding,
    normalize_response,
    repair_arguments,
)
from tests.fakes import load_fixture


def test_diff05_diff06_diff08_hunyuan_missing_id_and_fenced_args() -> None:
    raw = load_fixture("hunyuan_tool_call_missing_id.synthetic.json")
    out, fixes = normalize_response(raw, "hunyuan-turbo")
    choice = out["choices"][0]
    call = choice["message"]["tool_calls"][0]
    assert call["id"].startswith("call_") and call["type"] == "function"
    assert json.loads(call["function"]["arguments"]) == {"keyword": "华东", "limit": 5}
    assert choice["finish_reason"] == "tool_calls"
    assert out["model"] == "hunyuan-turbo" and out["object"] == "chat.completion"
    assert {"tool_call:id_filled", "tool_call:type_filled", "tool_call:arguments_repaired"} <= set(fixes)
    assert "id" not in raw["choices"][0]["message"]["tool_calls"][0]  # 原始样本没有被修改


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ({"a": 1}, {"a": 1}),
        ("", {}),
        (None, {}),
        ('{"a": 1, "b": "x', {"a": 1, "b": "x"}),
        ("好的，参数如下：{'a': 2}", {"a": 2}),
    ],
)
def test_diff06_repair_arguments(raw: object, expected: dict[str, int]) -> None:
    args, _ = repair_arguments(raw)
    assert json.loads(args) == expected


def test_diff06_unrepairable_arguments_raise_structured_error() -> None:
    with pytest.raises(GatewayError) as info:
        repair_arguments("完全不是 JSON")
    assert info.value.code == "invalid_tool_arguments" and info.value.status == 502


@pytest.mark.parametrize(
    ("raw", "has_tools", "expected"),
    [
        ("stop", False, "stop"),
        (None, False, "stop"),
        ("", False, "stop"),
        ("tool_call", True, "tool_calls"),
        ("function_call", False, "tool_calls"),
        ("stop", True, "tool_calls"),
        (None, True, "tool_calls"),
        ("max_tokens", False, "length"),
        ("length", True, "length"),
        ("sensitive", False, "content_filter"),
        ("weird_value", False, "stop"),
    ],
)
def test_diff08_finish_reason_mapping(raw: str | None, has_tools: bool, expected: str) -> None:
    assert map_finish_reason(raw, has_tools) == expected


def test_diff09_reasoning_content_kept_separately() -> None:
    out, _ = normalize_response(load_fixture("deepseek_reasoning.synthetic.json"), "deepseek-chat")
    msg = out["choices"][0]["message"]
    assert msg["reasoning_content"].startswith("客户处于")
    assert msg["content"] == "建议先安排一次技术交流。"
    assert out["choices"][0]["finish_reason"] == "stop"


def test_diff09_think_tag_and_legacy_function_call() -> None:
    out, fixes = normalize_response(load_fixture("qwen_think_tag.synthetic.json"), "qwen-plus")
    msg = out["choices"][0]["message"]
    assert msg["reasoning_content"] == "需要查一下商机"
    assert msg["content"] == ""
    assert "function_call" not in msg
    assert json.loads(msg["tool_calls"][0]["function"]["arguments"]) == {"opportunity_id": 42}
    assert out["choices"][0]["finish_reason"] == "tool_calls"
    assert "reasoning:think_tag_extracted" in fixes


def test_message_unknown_fields_dropped() -> None:
    raw = {"choices": [{"message": {"role": "assistant", "content": "x", "provider_specific_fields": {}}}]}
    out, _ = normalize_response(raw, "m")
    assert out["choices"][0]["message"] == {"role": "assistant", "content": "x"}
    assert out["id"].startswith("chatcmpl-")


def test_json_output_repaired_after_downgrade() -> None:
    resp = {"choices": [{"message": {"role": "assistant", "content": '```json\n{"price": 100,}\n```'}}]}
    out, fixes = ensure_json_content(resp)
    assert json.loads(out["choices"][0]["message"]["content"]) == {"price": 100}
    assert fixes == ["json_output:repaired"]


def test_embedding_normalized() -> None:
    out = normalize_embedding({"data": [[0.1, 0.2]], "usage": {"prompt_tokens": 3}}, "embed-default")
    assert out["data"] == [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}]
    assert out["usage"] == {"prompt_tokens": 3, "total_tokens": 3}
