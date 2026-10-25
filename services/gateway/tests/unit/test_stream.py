"""流式规范化：差异 #7 #8 #9 #10 #11。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.compat.errors import GatewayError
from app.compat.response import normalize_response
from app.compat.stream import (
    StreamState,
    estimate_tokens,
    finalize,
    process_chunk,
    pseudo_stream,
    sse_encode,
)
from tests.fakes import load_fixture


def _run(chunks: list[dict[str, Any]], prompt_tokens: int = 10) -> tuple[list[dict[str, Any]], StreamState]:
    state = StreamState(model="alias")
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        out += process_chunk(state, chunk)
    out += finalize(state, prompt_tokens)
    return out, state


def _assert_openai_chunks(out: list[dict[str, Any]]) -> None:
    for chunk in out:
        assert chunk["object"] == "chat.completion.chunk"
        assert chunk["model"] == "alias"
        assert len(chunk["choices"]) == 1 and "delta" in chunk["choices"][0]
    assert len({c["id"] for c in out}) == 1


def _tool_deltas(out: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c["choices"][0]["delta"]["tool_calls"][0] for c in out if "tool_calls" in c["choices"][0]["delta"]
    ]


def test_diff07_tool_fragments_accumulated_by_index() -> None:
    out, state = _run(load_fixture("qwen_stream_tool_fragments.synthetic.json")["chunks"])
    _assert_openai_chunks(out)
    calls = _tool_deltas(out)
    assert [c["index"] for c in calls] == [0, 1]
    assert calls[0]["id"] == "call_a1"
    assert calls[1]["id"].startswith("call_")  # 第二个调用上游没给 id，网关补齐
    assert json.loads(calls[0]["function"]["arguments"]) == {"keyword": "华东"}
    assert calls[1]["function"] == {"name": "list_products", "arguments": '{"category": "gpu"}'}
    assert "stream:tool_index_inferred" in state.fixes


def test_diff08_diff10_last_chunk_has_finish_and_estimated_usage() -> None:
    out, state = _run(load_fixture("qwen_stream_tool_fragments.synthetic.json")["chunks"])
    last = out[-1]
    assert last["choices"][0]["finish_reason"] == "tool_calls"
    assert last["usage"]["estimated"] is True
    usage = last["usage"]
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert "usage:estimated" in state.fixes
    assert all(c["choices"][0]["finish_reason"] is None for c in out[:-1])


def test_diff09_diff10_reasoning_streamed_and_upstream_usage_kept() -> None:
    out, _ = _run(load_fixture("deepseek_stream_text_usage.synthetic.json")["chunks"])
    _assert_openai_chunks(out)
    deltas = [c["choices"][0]["delta"] for c in out]
    assert deltas[0]["role"] == "assistant" and deltas[0]["reasoning_content"] == "想一下"
    assert "".join(d.get("content", "") for d in deltas) == "你好，我是 SalesPilot。"
    assert out[-1]["choices"][0]["finish_reason"] == "stop"
    assert out[-1]["usage"] == {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}
    assert out[0]["id"] == "synthetic-ds-stream-1"


def test_diff07_invalid_args_at_end_raise() -> None:
    bad = {"index": 0, "function": {"name": "a", "arguments": "完全不是"}}
    with pytest.raises(GatewayError):
        _run([{"choices": [{"delta": {"tool_calls": [bad]}}]}])


def test_empty_stream_still_well_formed() -> None:
    out, _ = _run([])
    assert out[0]["choices"][0]["delta"] == {"role": "assistant", "content": ""}
    assert out[-1]["choices"][0]["finish_reason"] == "stop"


def test_diff11_pseudo_stream_from_non_stream_response() -> None:
    raw = load_fixture("hunyuan_tool_call_missing_id.synthetic.json")
    resp, _ = normalize_response(raw, "hunyuan-turbo")
    chunks = pseudo_stream(resp, prompt_tokens=120)
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    call = chunks[1]["choices"][0]["delta"]["tool_calls"][0]
    assert call["index"] == 0 and call["id"] == resp["choices"][0]["message"]["tool_calls"][0]["id"]
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"
    assert chunks[-1]["usage"]["total_tokens"] == 150
    assert {c["object"] for c in chunks} == {"chat.completion.chunk"}


def test_diff11_pseudo_stream_splits_text() -> None:
    resp = {"id": "r", "model": "m", "choices": [{"message": {"content": "a" * 40}, "finish_reason": "stop"}]}
    chunks = pseudo_stream(resp, prompt_tokens=1, size=16)
    pieces = [c["choices"][0]["delta"].get("content") for c in chunks[1:-1]]
    assert pieces == ["a" * 16, "a" * 16, "a" * 8]
    assert chunks[-1]["usage"]["estimated"] is True


def test_estimate_tokens_and_sse_encode() -> None:
    assert estimate_tokens("你好") == 2
    assert estimate_tokens("abcdefgh") == 2
    assert sse_encode({"a": "中"}) == 'data: {"a": "中"}\n\n'
