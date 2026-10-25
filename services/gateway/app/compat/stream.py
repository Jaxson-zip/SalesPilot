"""流式规范化（差异 #7 #8 #9 #10 #11）。

纯函数 + 显式状态对象：`process_chunk(state, chunk)` 吃一片上游分片，返回要输出的 OpenAI 分片列表；
`finalize(state, ...)` 在上游结束时输出工具调用和最后一片（带 finish_reason 和 usage）。

取舍：工具调用分片先按 index 累积，结束时一次性输出「补齐 id、修好参数」的完整工具调用增量，
这样才能保证对 core 的承诺「arguments 一定是合法 JSON」；文本和推理内容仍然实时输出。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.compat.response import map_finish_reason, normalize_tool_call

PSEUDO_CHUNK_CHARS = 16


@dataclass
class ToolAcc:
    id: str | None = None
    name: str = ""
    arguments: str = ""


@dataclass
class StreamState:
    model: str
    id: str = field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    created: int = field(default_factory=lambda: int(time.time()))
    role_sent: bool = False
    content: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    tools: dict[int, ToolAcc] = field(default_factory=dict)
    last_index: int = 0
    finish_raw: str | None = None
    usage: dict[str, Any] | None = None
    fixes: list[str] = field(default_factory=list)
    upstream_id_seen: bool = False


# ---------- 用量估算（#10） ----------


def estimate_tokens(text: str) -> int:
    """粗略估算：中日韩字符按 1 token / 字，其余按 4 字符 / token。"""
    cjk = sum(1 for ch in text if "⺀" <= ch <= "鿿" or "가" <= ch <= "힯")
    return cjk + (len(text) - cjk + 3) // 4


def estimate_prompt_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for m in messages:
        content = m.get("content")
        text = content if isinstance(content, str) else json.dumps(content or "", ensure_ascii=False)
        total += estimate_tokens(text) + 4
        if m.get("tool_calls"):
            total += estimate_tokens(json.dumps(m["tool_calls"], ensure_ascii=False))
    return total


def normalize_usage(usage: dict[str, Any] | None, prompt_tokens: int, completion_text: str) -> dict[str, Any]:
    """有上游 usage 就规整字段，没有就本地估算并标记 estimated。"""
    if usage and usage.get("prompt_tokens") is not None:
        p = int(usage.get("prompt_tokens") or 0)
        c = int(usage.get("completion_tokens") or 0)
        return {
            "prompt_tokens": p,
            "completion_tokens": c,
            "total_tokens": int(usage.get("total_tokens") or p + c),
        }
    c = estimate_tokens(completion_text)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": c,
        "total_tokens": prompt_tokens + c,
        "estimated": True,
    }


# ---------- 分片处理 ----------


def make_chunk(
    state: StreamState,
    delta: dict[str, Any],
    finish_reason: str | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chunk: dict[str, Any] = {
        "id": state.id,
        "object": "chat.completion.chunk",
        "created": state.created,
        "model": state.model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        chunk["usage"] = usage
    return chunk


def _accumulate_tool_delta(state: StreamState, tc: dict[str, Any]) -> None:
    """#7：按 index 累积；index 缺失时根据 id 推断；id 只在第一片出现也能对上。"""
    idx = tc.get("index")
    if not isinstance(idx, int):
        known_ids = {t.id for t in state.tools.values()}
        if tc.get("id") and tc["id"] not in known_ids:
            idx = len(state.tools)
        else:
            idx = state.last_index if state.tools else 0
        state.fixes.append("stream:tool_index_inferred")
    acc = state.tools.setdefault(idx, ToolAcc())
    if tc.get("id") and not acc.id:
        acc.id = tc["id"]
    fn = tc.get("function") or {}
    if fn.get("name") and not acc.name:
        acc.name = fn["name"]
    args = fn.get("arguments")
    if isinstance(args, dict):
        args = json.dumps(args, ensure_ascii=False)
    if args:
        acc.arguments += args
    state.last_index = idx


def _clean_delta(state: StreamState, delta: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    if not state.role_sent:
        clean.update(role="assistant", content="")
        state.role_sent = True
    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
    if reasoning:
        clean["reasoning_content"] = reasoning
        state.reasoning.append(reasoning)
    content = delta.get("content")
    if content:
        clean["content"] = content
        state.content.append(content)
    return clean


def process_chunk(state: StreamState, chunk: dict[str, Any]) -> list[dict[str, Any]]:
    """吃一片上游分片，返回要立即输出的分片（只含 role / content / reasoning_content）。"""
    if chunk.get("usage"):
        state.usage = chunk["usage"]
    if chunk.get("id") and not state.upstream_id_seen:
        state.id, state.upstream_id_seen = str(chunk["id"]), True
    out: list[dict[str, Any]] = []
    for choice in chunk.get("choices") or []:
        if choice.get("index", 0) != 0:
            continue
        delta = choice.get("delta") or {}
        clean = _clean_delta(state, delta)
        for tc in delta.get("tool_calls") or []:
            _accumulate_tool_delta(state, tc)
        if delta.get("function_call"):
            _accumulate_tool_delta(state, {"index": 0, "function": delta["function_call"]})
        if choice.get("finish_reason"):
            state.finish_raw = choice["finish_reason"]
        if clean:
            out.append(make_chunk(state, clean))
    return out


def finalize(state: StreamState, prompt_tokens: int) -> list[dict[str, Any]]:
    """上游结束：输出补齐后的工具调用增量 + 最后一片（finish_reason + usage）。

    参数修不好时 normalize_tool_call 会抛 GatewayError，由调用方转成 error 事件。
    """
    out: list[dict[str, Any]] = []
    if not state.role_sent:
        out.append(make_chunk(state, {"role": "assistant", "content": ""}))
        state.role_sent = True
    args_text = ""
    for pos, idx in enumerate(sorted(state.tools)):
        acc = state.tools[idx]
        raw = {"id": acc.id, "type": "function", "function": {"name": acc.name, "arguments": acc.arguments}}
        call, fixes = normalize_tool_call(raw, pos)
        state.fixes += [f"stream:{f}" for f in fixes]
        args_text += call["function"]["arguments"]
        out.append(make_chunk(state, {"tool_calls": [{"index": pos, **call}]}))
    finish = map_finish_reason(state.finish_raw, bool(state.tools))
    if finish != state.finish_raw:
        state.fixes.append(f"finish_reason:{state.finish_raw}->{finish}")
    completion_text = "".join(state.content) + "".join(state.reasoning) + args_text
    usage = normalize_usage(state.usage, prompt_tokens, completion_text)
    if usage.get("estimated"):
        state.fixes.append("usage:estimated")
    out.append(make_chunk(state, {}, finish, usage))
    return out


# ---------- 伪流式（#11） ----------


def _split_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def pseudo_stream(
    resp: dict[str, Any], prompt_tokens: int, size: int = PSEUDO_CHUNK_CHARS
) -> list[dict[str, Any]]:
    """把已经规范化的非流式响应切成 OpenAI 流式分片。"""
    state = StreamState(model=resp.get("model", ""), id=resp.get("id") or StreamState(model="").id)
    state.created = int(resp.get("created") or state.created)
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    out = [make_chunk(state, {"role": "assistant", "content": ""})]
    if msg.get("reasoning_content"):
        out.append(make_chunk(state, {"reasoning_content": msg["reasoning_content"]}))
    for piece in _split_text(msg.get("content") or "", size):
        out.append(make_chunk(state, {"content": piece}))
    for pos, call in enumerate(msg.get("tool_calls") or []):
        out.append(make_chunk(state, {"tool_calls": [{"index": pos, **call}]}))
    text = (msg.get("content") or "") + json.dumps(msg.get("tool_calls") or "", ensure_ascii=False)
    usage = normalize_usage(resp.get("usage"), prompt_tokens, text)
    out.append(make_chunk(state, {}, choice.get("finish_reason") or "stop", usage))
    return out


# ---------- SSE 编码 ----------

SSE_DONE = "data: [DONE]\n\n"


def sse_encode(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
