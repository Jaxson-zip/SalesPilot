"""网关 HTTP 入口：对外完全是 OpenAI 格式。

POST /v1/chat/completions · POST /v1/embeddings · GET /v1/models · GET /health
"""

from __future__ import annotations

import hmac
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.backend import Backend, LiteLLMBackend
from app.compat.errors import GatewayError, classify_exception, error_body, invalid_param, unauthorized
from app.config import Settings, get_settings, merged_env
from app.logging import CallLog, setup_logging
from app.registry import Registry, load_registry
from app.router import GatewayRouter

REQUEST_ID_HEADER = "X-Request-ID"


class ChatCompletionRequest(BaseModel):
    """只校验关键字段，其余 OpenAI 参数原样透传给兼容层。"""

    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    messages: list[dict[str, Any]] = Field(min_length=1)
    stream: bool = False
    tools: list[dict[str, Any]] | None = None


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    input: str | list[str] | list[int] | list[list[int]]


def _effective_timeout(settings: Settings, registry: Registry, env: dict[str, str]) -> float:
    """GATEWAY_TIMEOUT_SECONDS 显式设置时优先，否则用 models.yaml 的 settings.timeout_seconds。"""
    if env.get("GATEWAY_TIMEOUT_SECONDS"):
        return settings.gateway_timeout_seconds
    return registry.settings.timeout_seconds


def _error_response(err: GatewayError, request: Request) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(error_body(err), status_code=err.status, headers={REQUEST_ID_HEADER: request_id})


def _install_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayError)
    async def _gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
        return _error_response(exc, request)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        param = ".".join(str(p) for p in first.get("loc", ())[1:]) or None
        return _error_response(invalid_param(str(first.get("msg", "invalid request")), param), request)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        err = GatewayError(500, 50001, "Internal gateway error", "api_error", "internal_error")
        return _error_response(err, request)

    @app.middleware("http")
    async def _request_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


async def _logged(stream: AsyncIterator[str], log: CallLog) -> AsyncIterator[str]:
    try:
        async for item in stream:
            yield item
    finally:
        log.emit()


def _model_card(registry: Registry, router: GatewayRouter, alias: str) -> dict[str, Any]:
    entry = registry.models[alias]
    return {
        "id": alias,
        "object": "model",
        "created": 0,
        "owned_by": "salespilot-gateway",
        "type": "model",
        "link": entry.link,
        "groups": registry.groups_of(alias),
        "capabilities": entry.capabilities.model_dump(),
        "available": entry.available,
        "unavailable_reason": entry.unavailable_reason,
        "last_call": router.health.get(alias),
    }


def _group_card(registry: Registry, name: str) -> dict[str, Any]:
    members = [registry.models[a] for a in registry.groups[name]]
    bool_caps = ("stream", "tools", "stream_tools", "json_mode", "embeddings")
    caps = {c: bool(members) and all(getattr(m.capabilities, c) for m in members) for c in bool_caps}
    return {
        "id": name,
        "object": "model",
        "created": 0,
        "owned_by": "salespilot-gateway",
        "type": "group",
        "members": [m.alias for m in members],
        "available_members": [m.alias for m in members if m.available],
        "capabilities": caps,
        "available": any(m.available for m in members),
    }


def _install_routes(
    app: FastAPI, registry: Registry, router: GatewayRouter, auth: Callable[..., None]
) -> None:
    @app.get("/health")
    async def health() -> dict[str, Any]:
        models = {
            a: {"available": e.available, "last_call": router.health.get(a)}
            for a, e in registry.models.items()
        }
        return {"status": "ok", "models": models}

    @app.get("/v1/models", dependencies=[Depends(auth)])
    async def list_models() -> dict[str, Any]:
        data = [_model_card(registry, router, a) for a in registry.models]
        data += [_group_card(registry, g) for g in registry.groups]
        return {"object": "list", "data": data}

    @app.post("/v1/chat/completions", dependencies=[Depends(auth)], response_model=None)
    async def chat_completions(body: ChatCompletionRequest, request: Request) -> Response | dict[str, Any]:
        payload = body.model_dump(exclude_none=True)
        log = CallLog(request.state.request_id, "chat", body.model, stream=body.stream)
        try:
            if body.stream:
                stream = await router.open_stream(payload, log)
                headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
                return StreamingResponse(
                    _logged(stream, log), media_type="text/event-stream", headers=headers
                )
            resp = await router.complete(payload, log)
        except Exception as exc:
            err = classify_exception(exc)
            log.status, log.error_code = "error", err.code
            log.emit()
            raise err from exc
        log.emit()
        return resp

    @app.post("/v1/embeddings", dependencies=[Depends(auth)])
    async def embeddings(body: EmbeddingRequest, request: Request) -> dict[str, Any]:
        log = CallLog(request.state.request_id, "embeddings", body.model)
        try:
            resp = await router.embed(body.model_dump(exclude_none=True), log)
        except Exception as exc:
            err = classify_exception(exc)
            log.status, log.error_code = "error", err.code
            log.emit()
            raise err from exc
        log.emit()
        return resp


def create_app(
    registry: Registry | None = None,
    backend: Backend | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """应用工厂。测试时注入 registry / backend（Fake），不访问外网。"""
    settings = settings or get_settings()
    setup_logging(settings.gateway_log_level)
    env = merged_env()
    registry = registry or load_registry(settings.models_path(), env)
    backend = backend or LiteLLMBackend(registry, _effective_timeout(settings, registry, env))
    router = GatewayRouter(registry, backend)

    def auth(request: Request) -> None:
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        if not token or not hmac.compare_digest(token.encode(), settings.gateway_internal_key.encode()):
            raise unauthorized()

    app = FastAPI(title="SalesPilot Model Gateway", version="0.1.0")
    app.state.registry = registry
    app.state.router = router
    _install_handlers(app)
    _install_routes(app, registry, router, auth)
    return app


app = create_app()
