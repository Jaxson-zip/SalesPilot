"""网页上的模型配置：内置厂商改 Key / 地址 / 协议、自定义厂商、默认模型分组、测试连接不回显 Key。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.overlay import custom_alias
from tests.fakes import TEST_ENV, FakeBackend, make_registry, upstream_error

KEY = "test-internal-key"
AUTH = {"Authorization": f"Bearer {KEY}"}
URL = "/v1/admin/config"
KIMI = {
    "id": "kimi",
    "protocol": "openai_compat",
    "api_base": "https://api.moonshot.example/v1",
    "api_key": "sk-kimi",
    "models": [
        {"model": "Moonshot-V1 8K", "kind": "chat", "capabilities": {"tools": True}},
        {"model": "kimi-embed", "kind": "embedding", "capabilities": {"dims": 4}},
    ],
}


def _client() -> tuple[TestClient, FakeBackend]:
    backend = FakeBackend({})
    app = create_app(
        registry=make_registry(), backend=backend, settings=Settings(gateway_internal_key=KEY), env=TEST_ENV
    )
    return TestClient(app), backend


def _put(client: TestClient, body: dict[str, Any]) -> Any:
    return client.put(URL, json=body, headers=AUTH)


def _builtin(state: dict[str, Any], var: str) -> dict[str, Any]:
    return next(p for p in state["builtin"] if p["var"] == var)


def _models(client: TestClient) -> dict[str, Any]:
    return {m["id"]: m for m in client.get("/v1/models", headers=AUTH).json()["data"]}


def test_admin_routes_require_internal_key() -> None:
    client, _ = _client()
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={}).status_code == 401
    assert client.post("/v1/admin/test", json={"var": "K_A"}).status_code == 401


def test_push_key_makes_model_available_without_restart() -> None:
    client, backend = _client()
    before = client.get(URL, headers=AUTH).json()
    assert before["version"] == ""
    missing = _builtin(before, "MISSING")
    assert missing["available"] is False and missing["env_configured"] is False
    assert missing["default_base"] == "http://upstream.invalid/v1"
    after = _put(client, {"version": "v1", "builtin": {"MISSING": {"key": "sk-web"}}}).json()
    assert after["version"] == "v1" and _builtin(after, "MISSING")["available"] is True
    assert _builtin(after, "MISSING")["key_overridden"] is True
    assert "sk-web" not in str(after)
    assert backend.resets == 1
    models = _models(client)
    assert models["m-nokey"]["available"] is True and "sk-web" not in str(models)
    # 下一次推送没带这个厂商：回到 .env（没有）→ 又不可用
    again = _put(client, {"version": "v2"}).json()
    assert _builtin(again, "MISSING")["available"] is False


def test_builtin_base_and_protocol_override() -> None:
    client, _ = _client()
    body = {
        "builtin": {"K_A": {"base": "https://proxy.example/v1", "protocol": "native", "adapter": "deepseek"}}
    }
    assert _put(client, body).status_code == 200
    registry = client.app.state.registry  # type: ignore[attr-defined]
    tools = registry.models["m-tools"]
    assert tools.api_base == "https://proxy.example/v1" and tools.api_key == "key-a"
    assert tools.litellm_model == "deepseek/x"
    assert registry.models["m-rerank"].link == "openai_compat"  # 重排不跟着改协议
    assert registry.models["m-pseudo"].api_base == "http://upstream.invalid/v1"  # 其他厂商不受影响
    # 改回 OpenAI 兼容：去掉适配名前缀
    _put(client, {"builtin": {"K_A": {"protocol": "openai_compat"}}})
    assert registry.models["m-tools"].litellm_model == "openai/x"
    # 原生协议必须写适配名；地址必须是 http(s)
    assert _put(client, {"builtin": {"K_A": {"protocol": "native"}}}).status_code == 400
    assert _put(client, {"builtin": {"K_A": {"base": "file:///etc/passwd"}}}).status_code == 400
    assert _put(client, {"builtin": {"PATH": {"key": "x"}}}).status_code == 400


def test_custom_provider_and_groups() -> None:
    client, _ = _client()
    chat, embed = custom_alias("kimi", "Moonshot-V1 8K"), custom_alias("kimi", "kimi-embed")
    assert chat == "kimi-moonshot-v1-8k"
    body = {
        "version": "v1",
        "custom": [KIMI],
        "groups": {"chat-agent": [chat, "m-plain", "m-tools"], "embed": [embed, "m-embed"]},
    }
    state = _put(client, body).json()
    assert state["custom"][0]["available"] is True
    assert "sk-kimi" not in str(state)
    # 不能调用工具的 m-plain 不进对话分组；向量分组只留一个
    assert state["groups"]["chat-agent"] == [chat, "m-tools"]
    assert state["groups"]["embed"] == [embed]
    assert state["group_defaults"]["embed"] == ["m-embed"]
    models = _models(client)
    assert models[chat]["capabilities"]["tools"] is True
    assert models[embed]["capabilities"]["embeddings"] is True
    # 删掉自定义厂商：分组回到 models.yaml 的默认
    state = _put(client, {"groups": body["groups"]}).json()
    assert state["groups"]["embed"] == ["m-embed"]
    assert state["groups"]["chat-agent"] == ["m-tools"]


def test_custom_provider_validation() -> None:
    client, _ = _client()
    assert _put(client, {"custom": [KIMI, KIMI]}).status_code == 400  # 重复 id
    clash = {**KIMI, "id": "m", "models": [{"model": "tools", "kind": "chat"}]}
    assert _put(client, {"custom": [clash]}).status_code == 400  # 别名 m-tools 和内置模型冲突
    assert _put(client, {"custom": [{**KIMI, "protocol": "native"}]}).status_code == 400
    assert _put(client, {"groups": {"g-chat": ["m-tools"]}}).status_code == 400


def test_probe_reports_errors_without_echoing_key() -> None:
    client, backend = _client()
    ok = client.post(
        "/v1/admin/test", json={"var": "K_A", "override": {"key": "sk-try"}}, headers=AUTH
    ).json()
    assert ok["ok"] is True and ok["model"] == "m-tools"
    assert backend.calls[-1] == ("m-tools", {"api_key": "sk-try", "api_base": "http://upstream.invalid/v1"})
    bad = client.post("/v1/admin/test", json={"var": "K_A", "override": {"key": "bad"}}, headers=AUTH).json()
    assert bad["ok"] is False and bad["error"].endswith("provided: ***")  # 上游回显的 Key 被替换
    # 不带 key：测当前生效的（这里是 .env 的值），表单上改的地址一起测
    client.post(
        "/v1/admin/test", json={"var": "K_B", "override": {"base": "https://other.example/v1"}}, headers=AUTH
    )
    assert backend.calls[-1] == ("m-pseudo", {"api_key": "key-b", "api_base": "https://other.example/v1"})
    empty = client.post("/v1/admin/test", json={"var": "MISSING"}, headers=AUTH).json()
    assert empty["ok"] is False and empty["error"] == "没有可用的 Key"


def test_probe_custom_model_detects_capabilities_and_dims() -> None:
    client, _ = _client()
    chat = {**KIMI, "models": [KIMI["models"][0]]}
    r = client.post("/v1/admin/test", json={"provider": chat, "detect": True}, headers=AUTH).json()
    assert r["ok"] is True and r["capabilities"]["tools"] is True
    embed = {**KIMI, "models": [KIMI["models"][1]]}
    r = client.post("/v1/admin/test", json={"provider": embed}, headers=AUTH).json()
    assert r["ok"] is True and r["dims"] == 4 and r["capabilities"] is None
    no_base = {**chat, "api_base": ""}
    r = client.post("/v1/admin/test", json={"provider": no_base}, headers=AUTH).json()
    assert r["error"] == "接口地址没有配置"


def test_probe_unreachable_message() -> None:
    client, backend = _client()

    async def down(entry: Any) -> dict[str, Any]:
        raise upstream_error(
            "InternalServerError", 500, "InternalServerError: OpenAIException - Connection error."
        )

    backend.probe = down  # type: ignore[method-assign]
    r = client.post("/v1/admin/test", json={"var": "K_A"}, headers=AUTH).json()
    assert r["error"].startswith("连不上这个地址") and "OpenAIException" not in r["error"]
