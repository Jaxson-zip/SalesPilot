"""工具基础设施：ToolSpec / ToolResult / ToolContext，以及统一执行入口 run_tool。

工具是 service 的薄包装：校验参数 → 调 service → 返回 {ok, summary, data}；工具里不写 SQL。
参数校验失败或 service 报错时返回 ok=false，不抛异常让图崩溃。
"""

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode

logger = logging.getLogger("core.agent")

Emit = Callable[[str, dict[str, Any]], None]
SessionFactory = Callable[[], AbstractContextManager[Session]]


class ToolResult(BaseModel):
    ok: bool
    summary: str
    data: Any = None
    error: dict[str, Any] | None = None


@dataclass
class ToolContext:
    """工具以当前登录用户的身份执行，数据权限与普通接口一致。"""

    user: CurrentUser
    session: SessionFactory
    thread_id: str = ""
    request_id: str = ""
    default_pack: str = "llm_deploy"
    extras: dict[str, Any] = field(default_factory=dict)


ToolFunc = Callable[[ToolContext, Any], ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    func: ToolFunc
    write: bool = False
    needs_confirm: bool = False

    def __post_init__(self) -> None:
        # 所有写工具统一走「准备 → 确认 → 执行」：不允许出现不用确认就能写库的工具
        if self.write and not self.needs_confirm:
            raise ValueError(f"写工具 {self.name} 必须 needs_confirm=True")

    def openai_schema(self) -> dict[str, Any]:
        """给 bind_tools 用的 OpenAI function 定义；系统注入的字段（INJECTED_ARGS）不暴露给模型。"""
        schema = self.args_model.model_json_schema()
        props = {k: v for k, v in schema.get("properties", {}).items() if k not in INJECTED_ARGS}
        required = [k for k in schema.get("required", []) if k not in INJECTED_ARGS]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {**schema, "properties": props, "required": required},
            },
        }


# 由系统填写、不让模型生成的参数：幂等键（模型编的不可靠）、行业包（由商机产品线决定）、
# 是否查全部行业包（由会话模式决定）
INJECTED_ARGS = frozenset({"idempotency_key", "pack_id", "all_packs"})


def inject_system_args(
    spec: ToolSpec, args: dict[str, Any], system: dict[str, Any]
) -> dict[str, Any]:
    """用系统值覆盖注入字段（模型即使传了也不采用）；工具没有该字段时不加。"""
    fields = spec.args_model.model_fields
    clean = {k: v for k, v in args.items() if k not in INJECTED_ARGS}
    return {**clean, **{k: v for k, v in system.items() if k in INJECTED_ARGS and k in fields}}


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _fail(code: int, message: str, data: Any = None) -> ToolResult:
    """结构化错误：error.data 带上 service 的附加信息（例如 40301 的 rule）。"""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return ToolResult(ok=False, summary=message, error=error)


def _execute(spec: ToolSpec, ctx: ToolContext, raw_args: dict[str, Any]) -> ToolResult:
    try:
        args = spec.args_model.model_validate(raw_args)
    except ValidationError as exc:
        return _fail(ErrorCode.VALIDATION, f"参数校验失败：{exc.errors()[0]['msg']}")
    try:
        return spec.func(ctx, args)
    except BizError as exc:
        return _fail(exc.code, exc.message, exc.data)
    except Exception:
        logger.exception("tool %s failed request_id=%s", spec.name, ctx.request_id)
        return _fail(ErrorCode.INTERNAL, "工具执行失败，请稍后重试或人工处理")


def run_tool(spec: ToolSpec, ctx: ToolContext, raw_args: dict[str, Any], emit: Emit) -> ToolResult:
    """执行工具并推送 tool.start / tool.end / tool.error 事件。"""
    call_id = new_call_id()
    emit("tool.start", {"call_id": call_id, "name": spec.name, "args": raw_args})
    started = time.perf_counter()
    result = _execute(spec, ctx, raw_args)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if spec.write:
        _audit(spec, ctx, result)
    if result.ok:
        payload = {"call_id": call_id, "summary": result.summary, "result": result.data}
        emit("tool.end", {**payload, "elapsed_ms": elapsed_ms})
    else:
        err = result.error or {}
        emit("tool.error", {"call_id": call_id, **err})
    return result


def _audit(spec: ToolSpec, ctx: ToolContext, result: ToolResult) -> None:
    """AI 写操作记入操作日志（source=agent），成功和失败都记。"""
    from app.crm.services import audit_service  # 避免 tools ↔ services 循环导入

    action, label = audit_service.TOOL_ACTIONS.get(spec.name, (f"agent.{spec.name}", spec.name))
    err = result.error or {}
    audit_service.record(
        ctx.user,
        audit_service.AuditEntry(
            action=action,
            label=label,
            source="agent",
            status=200 if result.ok else int(err.get("code") or 500),
            ok=result.ok,
            detail=result.summary[:500],
            request_id=ctx.request_id or None,
            extra={"thread_id": ctx.thread_id} if ctx.thread_id else None,
        ),
    )
