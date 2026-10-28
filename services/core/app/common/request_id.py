"""X-Request-ID：读取上游传入的请求 ID，没有则生成；存入 contextvar 供日志和网关调用透传。"""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.llm import usage

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        token = _request_id.set(rid)
        request.state.request_id = rid
        # 记录 AI 用量时用来归属到人和功能（见 app/llm/usage.py）
        usage_token = usage.bind(request.url.path, request.headers.get("authorization"))
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
            usage.reset(usage_token)
        response.headers[REQUEST_ID_HEADER] = rid
        return response
