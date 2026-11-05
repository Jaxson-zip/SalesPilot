"""网页登录态：token 放在 HttpOnly Cookie 里（JS 读不到，XSS 偷不走），不再存 localStorage。

- `HttpOnly; SameSite=Lax; Path=/`，HTTPS 下加 `Secure`；有效期与 JWT 一致。
- 浏览器发起的登录（带 Origin 请求头，浏览器对 POST 总会带且 JS 改不了）响应体里不返回 token，
  脚本 / 测试（不带 Origin）照旧拿到 token，用 Authorization: Bearer 调接口。
- Cookie 鉴权的写请求要带 X-Requested-With（见 app/common/auth.py 的 check_csrf）。
"""

from fastapi import Request, Response

from app.common.auth import SESSION_COOKIE
from app.common.config import get_settings


def _secure(request: Request) -> bool:
    configured = get_settings().cookie_secure
    if configured is not None:
        return configured
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or proto == "https"


def from_browser(request: Request) -> bool:
    """浏览器里的请求：响应体不带 token（只放 Cookie）。"""
    return bool(request.headers.get("origin"))


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=get_settings().jwt_expire_minutes * 60,
        path="/",
        secure=_secure(request),
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=_secure(request), httponly=True, samesite="lax"
    )
