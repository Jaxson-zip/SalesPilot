"""响应规范化（差异 #5 #6 #8 #9）。纯函数：输入上游（LiteLLM 转换后）的 dict，输出 OpenAI 格式 dict。"""

from __future__ import annotations

import copy
import json
import re
import time
import uuid
from typing import Any

from json_repair import repair_json

from app.compat.errors import GatewayError

FINISH_REASON_MAP: dict[str, str] = {
    "stop": "stop",
    "end_turn": "stop",
    "stop_sequence": "stop",
    "eos": "stop",
    "tool_calls": "tool_calls",
    "tool_call": "tool_calls",
    "function_call": "tool_calls",
    "tool_use": "tool_calls",
    "length": "length",
    "max_tokens": "length",
    "content_filter": "content_filter",
    "sensitive": "content_filter",
    "safety": "content_filter",
}
_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)
_THINK = re.compile(r"^\s*<think>(.*?)</think>\s*", re.DOTALL)

Fixes = list[str]


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:24]}"


def map_finish_reason(raw: str | None, has_tool_calls: bool) -> str:
    """#8：统一为 stop / tool_calls / length / content_filter。"""
    if has_tool_calls and raw in (None, "", "stop", "tool_call", "function_call", "tool_calls", "tool_use"):
        return "tool_calls"
    if not raw:
        return "stop"
    return FINISH_REASON_MAP.get(str(raw).lower(), "stop")


def repair_arguments(raw: Any) -> tuple[str, bool]:
    """#6：把工具参数修成合法 JSON 字符串（对象）。返回（参数, 是否修过）。修不好抛 GatewayError。"""
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False), True
    text = "" if raw is None else str(raw)
    if not text.strip():
        return "{}", True
    try:
        if isinstance(json.loads(text), dict):
            return text, False
    except json.JSONDecodeError:
        pass
    match = _FENCE.match(text)
    candidate = match.group(1) if match else text
    start = candidate.find("{")
    candidate = candidate[start:] if start >= 0 else candidate
    repaired = repair_json(candidate, return_objects=True)
    if not isinstance(repaired, dict):
        raise GatewayError(
            502,
            50201,
            f"Tool arguments are not valid JSON: {text[:200]}",
            "api_error",
            "invalid_tool_arguments",
        )
    return json.dumps(repaired, ensure_ascii=False), True


def normalize_tool_call(call: dict[str, Any], index: int) -> tuple[dict[str, Any], Fixes]:
    """#5 + #6：补 id / type，修复 arguments。"""
    fixes: Fixes = []
    fn = dict(call.get("function") or {})
    if not call.get("id"):
        fixes.append("tool_call:id_filled")
    if call.get("type") != "function":
        fixes.append("tool_call:type_filled")
    args, repaired = repair_arguments(fn.get("arguments"))
    if repaired:
        fixes.append("tool_call:arguments_repaired")
    out = {
        "id": call.get("id") or new_call_id(),
        "type": "function",
        "function": {"name": fn.get("name") or "", "arguments": args},
    }
    if "index" in call:
        out["index"] = call.get("index", index)
    return out, fixes


def split_reasoning(message: dict[str, Any]) -> Fixes:
    """#9：reasoning / <think> 统一挪到 reasoning_content（原地修改 message）。"""
    fixes: Fixes = []
    if message.get("reasoning") and not message.get("reasoning_content"):
        message["reasoning_content"] = message.pop("reasoning")
        fixes.append("reasoning:renamed")
    content = message.get("content")
    if isinstance(content, str):
        m = _THINK.match(content)
        if m:
            message["reasoning_content"] = (message.get("reasoning_content") or "") + m.group(1).strip()
            message["content"] = content[m.end() :]
            fixes.append("reasoning:think_tag_extracted")
    return fixes


def _legacy_function_call(message: dict[str, Any]) -> list[dict[str, Any]]:
    fc = message.pop("function_call", None)
    if not fc:
        return list(message.get("tool_calls") or [])
    return [{"type": "function", "function": fc}]


_MESSAGE_KEYS = ("role", "content", "tool_calls", "function_call", "reasoning_content", "reasoning")


def normalize_message(message: dict[str, Any]) -> tuple[dict[str, Any], Fixes]:
    msg = {k: v for k, v in (message or {}).items() if k in _MESSAGE_KEYS and v is not None}
    msg["role"] = msg.get("role") or "assistant"
    fixes = split_reasoning(msg)
    calls = _legacy_function_call(msg)
    if calls:
        normalized = []
        for i, call in enumerate(calls):
            fixed, call_fixes = normalize_tool_call(call, i)
            fixed.pop("index", None)
            normalized.append(fixed)
            fixes += call_fixes
        msg["tool_calls"] = normalized
    else:
        msg.pop("tool_calls", None)
    if msg.get("content") is None and not calls:
        msg["content"] = ""
    return msg, fixes


def normalize_response(resp: dict[str, Any], model: str) -> tuple[dict[str, Any], Fixes]:
    """非流式响应整理：补齐顶层字段、工具调用、finish_reason、推理字段。"""
    out = copy.deepcopy(resp)
    fixes: Fixes = []
    out["id"] = out.get("id") or f"chatcmpl-{uuid.uuid4().hex}"
    out["object"] = "chat.completion"
    out["created"] = int(out.get("created") or time.time())
    out["model"] = model
    choices = []
    for i, choice in enumerate(out.get("choices") or []):
        msg, msg_fixes = normalize_message(choice.get("message") or {})
        fixes += msg_fixes
        raw_finish = choice.get("finish_reason")
        finish = map_finish_reason(raw_finish, bool(msg.get("tool_calls")))
        if finish != raw_finish:
            fixes.append(f"finish_reason:{raw_finish}->{finish}")
        choices.append({"index": choice.get("index", i), "message": msg, "finish_reason": finish})
    out["choices"] = choices
    return out, fixes


def ensure_json_content(resp: dict[str, Any]) -> tuple[dict[str, Any], Fixes]:
    """response_format 降级后的本地校验：content 必须是合法 JSON，能修就修。"""
    fixes: Fixes = []
    for choice in resp.get("choices") or []:
        msg = choice.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, str) or msg.get("tool_calls"):
            continue
        try:
            json.loads(content)
            continue
        except json.JSONDecodeError:
            pass
        match = _FENCE.match(content)
        fixed = repair_json(match.group(1) if match else content, return_objects=True)
        if fixed in ("", None):
            raise GatewayError(
                502, 50201, "Model output is not valid JSON", "api_error", "invalid_json_output"
            )
        msg["content"] = json.dumps(fixed, ensure_ascii=False)
        fixes.append("json_output:repaired")
    return resp, fixes


def normalize_embedding(resp: dict[str, Any], model: str) -> dict[str, Any]:
    """Embedding 响应整理为 OpenAI list 结构。"""
    data = []
    for i, item in enumerate(resp.get("data") or []):
        vector = item.get("embedding") if isinstance(item, dict) else item
        index = item.get("index", i) if isinstance(item, dict) else i
        data.append({"object": "embedding", "index": index, "embedding": vector})
    usage = resp.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    return {
        "object": "list",
        "data": data,
        "model": model,
        "usage": {"prompt_tokens": prompt, "total_tokens": int(usage.get("total_tokens") or prompt)},
    }
