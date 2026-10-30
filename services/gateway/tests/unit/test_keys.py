"""网页上填写的厂商 Key：core 推送后立即生效、不回显 Key、测试连接。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fakes import TEST_ENV, FakeBackend, make_registry

KEY = "test-internal-key"
AUTH = {"Authorization": f"Bearer {KEY}"}


def _client() -> tuple[TestClient, FakeBackend]:
    backend = FakeBackend({})
    app = create_app(
        registry=make_registry(), backend=backend, settings=Settings(gateway_internal_key=KEY), env=TEST_ENV
    )
    return TestClient(app), backend


def _provider(body: dict, var: str) -> dict:
    return next(p for p in body["providers"] if p["var"] == var)


def test_admin_routes_require_internal_key() -> None:
    client, _ = _client()
    assert client.get("/v1/admin/providers").status_code == 401
    assert client.put("/v1/admin/keys", json={"keys": {}}).status_code == 401


def test_push_key_makes_model_available_without_restart() -> None:
    client, backend = _client()
    before = client.get("/v1/admin/providers", headers=AUTH).json()
    assert before["version"] == ""
    missing = _provider(before, "MISSING")
    assert missing == {
        "var": "MISSING",
        "models": ["m-nokey"],
        "env_configured": False,
        "overridden": False,
        "available": False,
    }
    after = client.put(
        "/v1/admin/keys", json={"keys": {"MISSING": "sk-web"}, "version": "v1"}, headers=AUTH
    ).json()
    assert after["version"] == "v1" and _provider(after, "MISSING")["available"] is True
    assert "sk-web" not in str(after)
    assert backend.resets == 1
    models = {m["id"]: m for m in client.get("/v1/models", headers=AUTH).json()["data"]}
    assert models["m-nokey"]["available"] is True and "sk-web" not in str(models)
    # 下一次推送没带这个变量：回到 .env（没有）→ 又不可用
    again = client.put("/v1/admin/keys", json={"keys": {}, "version": "v2"}, headers=AUTH).json()
    assert _provider(again, "MISSING")["available"] is False


def test_web_key_overrides_env() -> None:
    client, _ = _client()
    client.put("/v1/admin/keys", json={"keys": {"K_A": "sk-new"}, "version": "v1"}, headers=AUTH)
    registry = client.app.state.registry  # type: ignore[attr-defined]
    assert registry.models["m-tools"].api_key == "sk-new"
    assert registry.models["m-pseudo"].api_key == "key-b"  # 其他变量不受影响


def test_unknown_variable_rejected() -> None:
    client, _ = _client()
    resp = client.put("/v1/admin/keys", json={"keys": {"PATH": "x"}}, headers=AUTH)
    assert resp.status_code == 400


def test_probe_reports_errors_without_echoing_key() -> None:
    client, backend = _client()
    ok = client.post("/v1/admin/keys/test", json={"var": "K_A", "key": "sk-try"}, headers=AUTH).json()
    assert ok == {"ok": True, "model": "m-tools", "error": None}
    assert backend.calls[-1] == ("m-tools", {"api_key": "sk-try"})
    bad = client.post("/v1/admin/keys/test", json={"var": "K_A", "key": "bad"}, headers=AUTH).json()
    assert bad["ok"] is False and bad["error"].endswith("provided: ***")  # 上游回显的 Key 被替换
    # 不带 key：测当前生效的（这里是 .env 的值）
    client.post("/v1/admin/keys/test", json={"var": "K_B"}, headers=AUTH)
    assert backend.calls[-1] == ("m-pseudo", {"api_key": "key-b"})
    empty = client.post("/v1/admin/keys/test", json={"var": "MISSING"}, headers=AUTH).json()
    assert empty["ok"] is False and empty["error"] == "没有可用的 Key"
