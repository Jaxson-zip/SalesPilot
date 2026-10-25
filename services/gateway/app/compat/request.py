"""请求规范化（差异 #1–#4）。全部是纯函数：输入 OpenAI 请求 dict + 能力表，输出新请求和降级记录。"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from app.compat.errors import invalid_param
from app.registry import Capabilities

TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
REQUIRED_TOOL_HINT = "你必须调用至少一个提供的工具来完成本次回答，不要直接用文字回答。"
JSON_HINT = "请只输出一个合法的 JSON 对象，不要输出 Markdown 代码块或任何多余文字。"
_UNSUPPORTED_SCHEMA_KEYS = ("default", "examples", "$schema", "$id", "title", "format", "pattern")

Downgrades = list[str]


def normalize_request(body: dict[str, Any], caps: Capabilities) -> tuple[dict[str, Any], Downgrades]:
    """按目标模型能力规范化请求，返回（新请求, 降级说明列表）。不修改入参。"""
    req = copy.deepcopy(body)
    downgrades: Downgrades = []
    hints: list[str] = []
    hints += _downgrade_params(req, caps, downgrades)
    _map_param_names(req, caps, downgrades)
    _normalize_tools(req, caps, downgrades)
    req["messages"] = normalize_messages(req.get("messages") or [], caps, hints, downgrades)
    return req, downgrades


# ---------- #1 参数不被支持 ----------


def _downgrade_params(req: dict[str, Any], caps: Capabilities, downgrades: Downgrades) -> list[str]:
    hints: list[str] = []
    if req.get("tool_choice") == "required" and not caps.tool_choice_required:
        req["tool_choice"] = "auto"
        hints.append(REQUIRED_TOOL_HINT)
        downgrades.append("tool_choice:required->auto")
    if "parallel_tool_calls" in req and not caps.parallel_tool_calls:
        req.pop("parallel_tool_calls")
        downgrades.append("parallel_tool_calls:dropped")
    if "seed" in req and not caps.seed:
        req.pop("seed")
        downgrades.append("seed:dropped")
    hints += _downgrade_response_format(req, caps, downgrades)
    return hints


def _downgrade_response_format(req: dict[str, Any], caps: Capabilities, downgrades: Downgrades) -> list[str]:
    fmt = req.get("response_format")
    if not isinstance(fmt, dict):
        return []
    kind = fmt.get("type")
    if kind == "json_schema" and not caps.json_schema:
        schema = (fmt.get("json_schema") or {}).get("schema")
        hint = JSON_HINT + (f"\nJSON Schema：{json.dumps(schema, ensure_ascii=False)}" if schema else "")
        if caps.json_mode:
            req["response_format"] = {"type": "json_object"}
            downgrades.append("response_format:json_schema->json_object")
        else:
            req.pop("response_format")
            downgrades.append("response_format:json_schema->prompt")
        return [hint]
    if kind == "json_object":
        if not caps.json_mode:
            req.pop("response_format")
            downgrades.append("response_format:json_object->prompt")
        return [JSON_HINT]  # json_object 模式要求提示词里出现 "JSON"
    return []


def wants_json(body: dict[str, Any]) -> bool:
    """原始请求是否要求 JSON 输出（降级后需要网关本地校验 / 修复）。"""
    fmt = body.get("response_format")
    return isinstance(fmt, dict) and fmt.get("type") in ("json_object", "json_schema")


# ---------- #2 参数命名和范围 ----------


def _clamp(value: Any, low: float, high: float) -> Any:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return min(max(value, low), high)
    return value


def _map_param_names(req: dict[str, Any], caps: Capabilities, downgrades: Downgrades) -> None:
    other = "max_completion_tokens" if caps.max_tokens_param == "max_tokens" else "max_tokens"
    if other in req:
        value = req.pop(other)
        req.setdefault(caps.max_tokens_param, value)
        downgrades.append(f"{other}->{caps.max_tokens_param}")
    limit = caps.max_output_tokens
    key = caps.max_tokens_param
    if limit and isinstance(req.get(key), int) and req[key] > limit:
        req[key] = limit
        downgrades.append(f"{key}:clamped")
    for name, high in (("temperature", caps.temperature_max), ("top_p", 1.0)):
        if name in req and req[name] is not None:
            clamped = _clamp(req[name], 0.0, high)
            if clamped != req[name]:
                req[name] = clamped
                downgrades.append(f"{name}:clamped")


# ---------- #3 消息格式 ----------


def _text_of(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content)


def normalize_messages(
    messages: list[dict[str, Any]], caps: Capabilities, hints: list[str], downgrades: Downgrades
) -> list[dict[str, Any]]:
    """合并 system 并放到首位；content: null → ""；修正工具结果消息顺序。"""
    msgs = [dict(m) for m in messages]
    system_texts = [_text_of(m.get("content")) for m in msgs if m.get("role") == "system"]
    others = [m for m in msgs if m.get("role") != "system"]
    if len(system_texts) > 1 or (system_texts and msgs[0].get("role") != "system"):
        downgrades.append("messages:system_merged")
    system_texts += hints
    for m in others:
        if m.get("content") is None:
            m["content"] = ""
        elif isinstance(m["content"], list) and not caps.content_parts:
            m["content"] = _text_of(m["content"])
            downgrades.append("messages:content_parts_flattened")
    ordered = reorder_tool_messages(others, downgrades)
    if system_texts:
        return [{"role": "system", "content": "\n\n".join(t for t in system_texts if t)}, *ordered]
    return ordered


def reorder_tool_messages(msgs: list[dict[str, Any]], downgrades: Downgrades) -> list[dict[str, Any]]:
    """保证每条带 tool_calls 的 assistant 消息后面紧跟它对应的 tool 消息。

    - 顺序乱了：挪到对应 assistant 之后；
    - 缺少结果：补一条空结果（多数厂商缺结果会直接 400）；
    - 找不到对应调用的 tool 消息：参数错误 40001。
    """
    results = {m.get("tool_call_id"): m for m in msgs if m.get("role") == "tool"}
    used: set[Any] = set()
    placeholders: set[int] = set()
    out: list[dict[str, Any]] = []
    for m in msgs:
        if m.get("role") == "tool":
            continue
        out.append(m)
        for call in m.get("tool_calls") or []:
            call_id = call.get("id")
            if call_id in results:
                out.append(results[call_id])
                used.add(call_id)
            else:
                filled = {"role": "tool", "tool_call_id": call_id, "content": ""}
                placeholders.add(id(filled))
                out.append(filled)
                downgrades.append("messages:missing_tool_result_filled")
    orphans = [cid for cid in results if cid not in used]
    if orphans:
        raise invalid_param(f"tool messages without matching tool_calls: {orphans}", "messages")
    if [id(m) for m in out if id(m) not in placeholders] != [id(m) for m in msgs]:
        downgrades.append("messages:tool_results_reordered")
    return out


# ---------- #4 工具定义 ----------


def _normalize_tools(req: dict[str, Any], caps: Capabilities, downgrades: Downgrades) -> None:
    tools = req.get("tools")
    if not tools:
        return
    for tool in tools:
        name = (tool.get("function") or {}).get("name", "")
        if not TOOL_NAME_PATTERN.match(str(name)):
            raise invalid_param(f"invalid tool name '{name}', must match ^[a-zA-Z0-9_-]{{1,64}}$", "tools")
        tool.setdefault("type", "function")
    if caps.simple_schema:
        for tool in tools:
            fn = tool["function"]
            if "parameters" in fn:
                fn["parameters"] = simplify_schema(fn["parameters"])
        downgrades.append("tools:schema_simplified")


def simplify_schema(schema: Any) -> Any:
    """去掉不被支持的关键字；anyOf/oneOf 取第一个非 null 分支。"""
    if isinstance(schema, list):
        return [simplify_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    result: dict[str, Any] = {}
    for union_key in ("anyOf", "oneOf"):
        if union_key in schema:
            branches = [b for b in schema[union_key] if not (isinstance(b, dict) and b.get("type") == "null")]
            picked = simplify_schema(branches[0]) if branches else {"type": "string"}
            rest = {k: v for k, v in schema.items() if k != union_key}
            return {**simplify_schema(rest), **picked}
    for key, value in schema.items():
        if key in _UNSUPPORTED_SCHEMA_KEYS and not isinstance(value, dict):
            continue
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: simplify_schema(v) for k, v in value.items()}
        else:
            result[key] = simplify_schema(value)
    return result
