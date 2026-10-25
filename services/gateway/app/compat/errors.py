"""错误统一（差异 #13）：各家 / LiteLLM 异常 → OpenAI 错误结构 + 网关错误码。

纯函数：只看异常的类名、status_code 和文本，不 import litellm，方便离线测试。
错误码见 docs/开发规范.md §8.2。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 网关错误码（与开发规范 §8.2 一致）
CODE_INVALID_PARAM = 40001
CODE_CAPABILITY_MISMATCH = 40002
CODE_UNAUTHORIZED = 40101
CODE_NOT_FOUND = 40401
CODE_RATE_LIMITED = 42901
CODE_INTERNAL = 50001
CODE_UPSTREAM = 50201
CODE_TIMEOUT = 50401


@dataclass
class GatewayError(Exception):
    """网关内部统一异常，最终由 main.py 转成 OpenAI 错误结构。"""

    status: int
    gateway_code: int
    message: str
    type: str = "api_error"
    code: str | None = None
    param: str | None = None
    details: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__(self.message)


def error_body(err: GatewayError) -> dict[str, Any]:
    """生成 OpenAI 风格错误体，额外带 gateway_code（以及多模型尝试明细）。"""
    body: dict[str, Any] = {
        "message": err.message,
        "type": err.type,
        "param": err.param,
        "code": err.code,
        "gateway_code": err.gateway_code,
    }
    if err.details:
        body["attempts"] = err.details
    return {"error": body}


def invalid_param(message: str, param: str | None = None) -> GatewayError:
    return GatewayError(400, CODE_INVALID_PARAM, message, "invalid_request_error", "invalid_param", param)


def capability_mismatch(message: str) -> GatewayError:
    return GatewayError(
        400, CODE_CAPABILITY_MISMATCH, message, "invalid_request_error", "capability_mismatch"
    )


def unauthorized(message: str = "Invalid gateway key") -> GatewayError:
    return GatewayError(401, CODE_UNAUTHORIZED, message, "authentication_error", "invalid_api_key")


def model_not_found(name: str) -> GatewayError:
    return GatewayError(
        404,
        CODE_NOT_FOUND,
        f"Model or group '{name}' not found",
        "invalid_request_error",
        "model_not_found",
        "model",
    )


def _text_of(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}".lower()


def _status_of(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


def classify_exception(exc: BaseException) -> GatewayError:
    """把任意上游异常归类为 GatewayError。已经是 GatewayError 的原样返回。"""
    if isinstance(exc, GatewayError):
        return exc
    name = type(exc).__name__.lower()
    text = _text_of(exc)
    status = _status_of(exc)
    msg = str(exc)[:500] or type(exc).__name__
    if "contextwindow" in name or "context_length" in text or "maximum context" in text:
        return GatewayError(400, CODE_INVALID_PARAM, msg, "invalid_request_error", "context_length_exceeded")
    if "contentpolicy" in name or "content_filter" in text or "data_inspection" in text:
        return GatewayError(400, CODE_INVALID_PARAM, msg, "invalid_request_error", "content_filter")
    if "authentication" in name or status in (401, 403):
        return GatewayError(401, CODE_UNAUTHORIZED, msg, "authentication_error", "upstream_auth")
    if "ratelimit" in name or status == 429:
        return GatewayError(429, CODE_RATE_LIMITED, msg, "rate_limit_error", "rate_limit_exceeded")
    if "timeout" in name or "timed out" in text or status in (408, 504):
        return GatewayError(504, CODE_TIMEOUT, msg, "timeout_error", "timeout")
    if status == 400 or "badrequest" in name:
        return GatewayError(400, CODE_INVALID_PARAM, msg, "invalid_request_error", "upstream_bad_request")
    return GatewayError(502, CODE_UPSTREAM, msg, "api_error", "upstream_error")


def should_failover(err: GatewayError) -> bool:
    """是否值得切到分组里的下一个模型。内容审核、我们自己的参数错误不切换。"""
    return err.code not in ("content_filter", "invalid_param", "capability_mismatch")


def aggregate_errors(attempts: list[tuple[str, GatewayError]], is_group: bool) -> GatewayError:
    """分组内所有模型都失败后，给出最终错误。"""
    if not attempts:
        return GatewayError(502, CODE_UPSTREAM, "No available model", "api_error", "no_available_model")
    last = attempts[-1][1]
    details = [{"model": alias, "status": e.status, "code": e.code} for alias, e in attempts]
    if not is_group:
        last.details = details
        return last
    statuses = {e.status for _, e in attempts}
    if statuses == {429}:
        return GatewayError(
            429,
            CODE_RATE_LIMITED,
            "All models in group are rate limited",
            "rate_limit_error",
            "rate_limit_exceeded",
            details=details,
        )
    if statuses == {504}:
        return GatewayError(
            504,
            CODE_TIMEOUT,
            "All models in group timed out",
            "timeout_error",
            "timeout",
            details=details,
        )
    if last.code in ("context_length_exceeded", "content_filter"):
        last.details = details
        return last
    return GatewayError(
        502,
        CODE_UPSTREAM,
        "All models in group failed",
        "api_error",
        "upstream_error",
        details=details,
    )
