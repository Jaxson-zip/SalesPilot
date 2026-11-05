"""操作日志中间件：网页上的每个写请求（含失败、被拒）记一条操作日志。

纯 ASGI 中间件（不包装响应体，SSE 流式接口不受影响）；只看方法、路径和响应，
不读请求体。用户身份从 Authorization 或登录 Cookie 解析，令牌无效时记为匿名。
路径里没有对象 id 的（新建、催办这类 id 在请求体里的），从响应 data.id / data.target_id 取，
日志才能定位到具体单据。
"""

import json
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.auth import CurrentUser, decode_token, request_token
from app.common.client_ip import resolve_client_ip
from app.common.errors import BizError
from app.common.request_id import get_request_id
from app.crm.services import audit_service

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# 只截响应开头这么多字节：够解析 code / message 和新建对象的 id；更大的响应解析失败就不取 id
CAPTURE_LIMIT = 16384


def _user(scope: Scope) -> CurrentUser | None:
    conn = HTTPConnection(scope)
    token, _ = request_token(conn.headers.get("authorization"), conn.cookies)
    if not token:
        return None
    try:
        return decode_token(token)
    except BizError:
        return None


def _ip(scope: Scope) -> str | None:
    real_ip = next(
        (v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"x-real-ip"), None
    )
    client = scope.get("client")
    return resolve_client_ip(real_ip, client[0] if client else None)


class AuditMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        method = scope.get("method", "")
        hit = (
            audit_service.match_route(method, scope.get("path", ""))
            if scope["type"] == "http" and method in WRITE_METHODS
            else None
        )
        if hit is None:
            await self.app(scope, receive, send)
            return
        status = {"code": 500}
        body: dict[str, Any] = {"chunks": [], "size": 0}
        # 同步接口在线程池里跑，拿到的是上下文的副本；列表对象是同一个，业务代码写进去这里看得到
        notes = audit_service.begin_notes()

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            elif message["type"] == "http.response.body" and body["size"] < CAPTURE_LIMIT:
                chunk = message.get("body", b"")
                body["chunks"].append(chunk)
                body["size"] += len(chunk)
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            action, label, target = hit
            code, msg, data_id = _biz(b"".join(body["chunks"]))
            ok = status["code"] < 400 and code == 0
            entry = audit_service.AuditEntry(
                action=action,
                label=label,
                method=method,
                path=scope.get("path", "")[:300],
                target_id=target or data_id,
                status=status["code"] if code in (0, None) else code,
                ok=ok,
                detail=("；".join(notes)[:500] or None) if ok else msg,
                ip=_ip(scope),
                request_id=get_request_id() or None,
            )
            await run_in_threadpool(audit_service.record, _user(scope), entry)


def _biz(raw: bytes) -> tuple[int | None, str | None, str | None]:
    """统一响应 {code, message, data}：业务失败也是 HTTP 200，需要看 code；顺带取对象 id。"""
    try:
        resp = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, None, None
    if not isinstance(resp, dict):
        return None, None, None
    code = resp.get("code")
    data = resp.get("data")
    oid = (data.get("id") or data.get("target_id")) if isinstance(data, dict) else None
    return (
        (code if isinstance(code, int) else None),
        resp.get("message"),
        str(oid)[:100] if oid else None,
    )
