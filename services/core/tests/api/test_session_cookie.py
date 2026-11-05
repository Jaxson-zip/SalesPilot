"""登录态放 HttpOnly Cookie：浏览器登录不返回 token、Cookie 鉴权、CSRF 请求头、退出登录。"""

import pytest
from fastapi.testclient import TestClient

from app.common.auth import CSRF_HEADER, SESSION_COOKIE
from app.common.config import get_settings

LOGIN = "/api/auth/mock-login"
BROWSER = {"Origin": "http://127.0.0.1:3000"}
CSRF = {CSRF_HEADER: "XMLHttpRequest"}


def _set_cookie(r: object) -> str:
    header = r.headers.get("set-cookie", "")  # type: ignore[attr-defined]
    assert header.startswith(f"{SESSION_COOKIE}="), header
    return header.lower()


def test_script_login_returns_token_and_cookie(client: TestClient) -> None:
    r = client.post(LOGIN, json={"role": "sales"})
    assert r.json()["code"] == 0
    assert r.json()["data"]["token"]
    cookie = _set_cookie(r)
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert "secure" not in cookie  # 本地 HTTP 不加 Secure，否则浏览器不回传


def test_browser_login_hides_token_and_cookie_authenticates(client: TestClient) -> None:
    r = client.post(LOGIN, json={"role": "manager"}, headers=BROWSER | CSRF)
    body = r.json()
    assert body["code"] == 0 and body["data"]["token"] is None
    assert body["data"]["user"]["role"] == "manager"
    _set_cookie(r)
    me = client.get("/api/me").json()  # TestClient 自动带上 Cookie，不带 Authorization
    assert me["code"] == 0 and me["data"]["role"] == "manager"


def test_cookie_write_without_csrf_header_rejected(client: TestClient) -> None:
    client.post(LOGIN, json={"role": "sales"}, headers=BROWSER)
    body = {"old_password": "wrong-password", "new_password": "x"}
    missing = client.post("/api/auth/password", json=body)
    assert missing.status_code == 403
    assert missing.json()["code"] == 40301 and missing.json()["data"]["rule"] == "csrf"
    # 带上请求头就通过 CSRF 校验，走到业务校验（原密码不对）
    passed = client.post("/api/auth/password", json=body, headers=CSRF).json()
    assert passed["code"] == 40001 and passed["data"]["rule"] == "wrong_password"


def test_bearer_write_needs_no_csrf_header(client: TestClient) -> None:
    token = client.post(LOGIN, json={"role": "sales"}).json()["data"]["token"]
    client.cookies.clear()
    body = {"old_password": "wrong-password", "new_password": "x"}
    r = client.post("/api/auth/password", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.json()["data"]["rule"] == "wrong_password"


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post(LOGIN, json={"role": "sales"}, headers=BROWSER)
    assert client.get("/api/me").json()["code"] == 0
    r = client.post("/api/auth/logout", headers=CSRF)
    assert r.json()["code"] == 0
    cookie = _set_cookie(r)
    assert "max-age=0" in cookie
    assert client.get("/api/me").status_code == 401


def test_logout_without_session_ok(client: TestClient) -> None:
    assert client.post("/api/auth/logout").json()["code"] == 0


def test_secure_cookie_behind_https_proxy(client: TestClient) -> None:
    r = client.post(LOGIN, json={"role": "sales"}, headers={"X-Forwarded-Proto": "https"})
    assert "secure" in _set_cookie(r)


def test_secure_cookie_forced_by_setting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    assert "secure" in _set_cookie(client.post(LOGIN, json={"role": "sales"}))


def test_invalid_cookie_unauthorized(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "x.y.z")
    assert client.get("/api/me").json()["code"] == 40101
