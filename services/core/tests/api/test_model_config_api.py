"""模型接入：内置厂商、自定义厂商、默认模型、切换向量模型重建索引；加密存库、不回显 Key。"""

import time
import uuid
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.common.config import get_settings
from app.common.db import session_scope
from app.crm.models import AuditLog, Integration, KbChunk
from app.crm.services import model_config_service as svc
from app.llm import client as llm_client
from tests.api.conftest import ADMIN_H, MANAGER_H

URL = "/api/integrations/models"
SECRET = "sk-test-0123456789abcd"
KIMI = {
    "name": "Kimi",
    "protocol": "openai_compat",
    "api_base": "https://api.moonshot.cn/v1",
    "key": "sk-kimi-0123456789",
    "models": [
        {"model": "moonshot-v1-8k", "kind": "chat", "capabilities": {"tools": True}},
        {"model": "kimi-embed", "kind": "embedding", "capabilities": {"dims": 1024}},
    ],
}


def _model(alias: str, kind: str = "chat", tools: bool = True, dims: int | None = None) -> dict:
    return {
        "alias": alias,
        "model": alias,
        "link": "openai_compat",
        "kind": kind,
        "tools": tools,
        "dims": dims,
    }


class FakeGateway:
    """模拟网关的 /v1/admin/*：记录推送的配置，按推送内容计算可用性和分组。"""

    BUILTIN: ClassVar[dict[str, list[dict]]] = {
        "HUNYUAN_API_KEY": [
            _model("hunyuan-turbo"),
            _model("embed-default", "embedding", False, 1024),
        ],
        "DEEPSEEK_API_KEY": [_model("deepseek-chat")],
    }
    DEFAULTS: ClassVar[dict[str, list[str]]] = {
        "chat-agent": ["deepseek-chat"],
        "embed": ["embed-default"],
        "rerank": [],
    }

    def __init__(self) -> None:
        self.config: dict[str, Any] = {"version": "", "builtin": {}, "custom": [], "groups": {}}
        self.env = {"DEEPSEEK_API_KEY"}
        self.down = False
        self.pushes = 0
        self.tested: list[dict[str, Any]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict:
        if self.down:
            raise svc.BizError(svc.ErrorCode.UPSTREAM, "down")
        if path == "config" and method == "PUT":
            self.config = dict(body or {})
            self.pushes += 1
        if path == "test":
            return self._test(body or {})
        return self._state()

    def _test(self, body: dict[str, Any]) -> dict:
        self.tested.append(body)
        if body.get("provider"):
            p = body["provider"]
            m = p["models"][0]
            dims = m["capabilities"].get("dims") or 1024 if m["kind"] == "embedding" else None
            caps = {"tools": True, "stream": True, "stream_tools": False, "json_mode": True}
            alias = svc.custom_alias(p["id"], m["model"])
            ok = p["api_key"] != "sk-wrong-key"
            return {
                "ok": ok,
                "model": alias,
                "dims": dims,
                "capabilities": caps if body["detect"] else None,
            }
        return {"ok": body["override"]["key"] != "sk-wrong-key", "model": "m", "error": None}

    def _state(self) -> dict:
        builtin = []
        for var, models in self.BUILTIN.items():
            ov = self.config["builtin"].get(var, {})
            available = bool(ov.get("key")) or var in self.env
            builtin.append(
                {
                    "var": var,
                    "env_configured": var in self.env,
                    "default_base": "https://official.example/v1",
                    "available": available,
                    "models": [
                        {**m, "available": available, "unavailable_reason": None} for m in models
                    ],
                }
            )
        custom = []
        for p in self.config["custom"]:
            models = [
                {
                    **_model(
                        svc.custom_alias(p["id"], m["model"]),
                        m["kind"],
                        m["capabilities"]["tools"],
                        m["capabilities"].get("dims"),
                    ),
                    "available": bool(p["api_key"]),
                    "unavailable_reason": None,
                }
                for m in p["models"]
            ]
            custom.append({"id": p["id"], "available": bool(p["api_key"]), "models": models})
        return {
            "version": self.config["version"],
            "builtin": builtin,
            "custom": custom,
            "groups": {**self.DEFAULTS, **self.config["groups"]},
            "group_defaults": self.DEFAULTS,
        }


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGateway]:
    fake = FakeGateway()
    monkeypatch.setattr(llm_client, "gateway_admin", fake)
    yield fake
    with session_scope() as db:
        db.execute(delete(Integration).where(Integration.kind == svc.KIND))


def _builtin(data: dict, var: str) -> dict:
    return next(p for p in data["builtin"] if p["var"] == var)


def _offline_status() -> dict:
    with session_scope() as db:
        return svc._status(db, svc._load(db), None).model_dump()


def _put_builtin(client: TestClient, **body: Any) -> Any:
    return client.put(f"{URL}/builtin", json={"var": "HUNYUAN_API_KEY", **body}, headers=ADMIN_H)


def test_only_admin(client: TestClient, gateway: FakeGateway) -> None:
    assert client.get(URL, headers=MANAGER_H).status_code == 403
    assert _put_builtin(client).status_code == 200
    r = client.put(
        f"{URL}/builtin", json={"var": "HUNYUAN_API_KEY", "key": SECRET}, headers=MANAGER_H
    )
    assert r.status_code == 403
    assert client.put(f"{URL}/custom/kimi", json=KIMI, headers=MANAGER_H).status_code == 403


def test_builtin_key_encrypted_pushed_and_masked(client: TestClient, gateway: FakeGateway) -> None:
    before = client.get(URL, headers=ADMIN_H).json()["data"]
    assert (
        before["gateway_ok"] is True and before["embedding_dims"] == get_settings().embedding_dims
    )
    assert _builtin(before, "HUNYUAN_API_KEY")["key_source"] == "none"
    assert _builtin(before, "DEEPSEEK_API_KEY")["key_source"] == "env"
    r = _put_builtin(client, key=f"  {SECRET} ")
    hunyuan = _builtin(r.json()["data"], "HUNYUAN_API_KEY")
    assert hunyuan["key_source"] == "web" and hunyuan["tail"] == "abcd" and hunyuan["available"]
    assert hunyuan["label"] == "腾讯混元" and hunyuan["saved_by"] == "周敏"
    assert SECRET not in r.text
    assert (
        gateway.config["builtin"]["HUNYUAN_API_KEY"]["key"] == SECRET and gateway.config["version"]
    )
    with session_scope() as db:
        row = db.scalar(select(Integration).where(Integration.kind == svc.KIND))
        assert row is not None and SECRET not in str(row.config)  # 库里是密文
        log = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "settings.model_builtin")
            .order_by(AuditLog.created_at.desc())
        )
        assert log is not None and SECRET not in str(log.__dict__)
    # 只改地址和协议：Key 不动
    r = _put_builtin(client, base="https://proxy.example/v1", protocol="native", adapter="openai")
    hunyuan = _builtin(r.json()["data"], "HUNYUAN_API_KEY")
    assert hunyuan["key_source"] == "web" and hunyuan["base"] == "https://proxy.example/v1"
    pushed = gateway.config["builtin"]["HUNYUAN_API_KEY"]
    assert pushed == {
        "key": SECRET,
        "base": "https://proxy.example/v1",
        "protocol": "native",
        "adapter": "openai",
    }
    # 清除 Key、恢复默认地址：回到 .env（这里没有），配置版本回到空
    cleared = _put_builtin(client, key="")
    assert _builtin(cleared.json()["data"], "HUNYUAN_API_KEY")["key_source"] == "none"
    assert gateway.config["version"] == "" and gateway.config["builtin"] == {}


def test_rejects_bad_input(client: TestClient, gateway: FakeGateway) -> None:
    unknown = client.put(
        f"{URL}/builtin", json={"var": "OPENAI_API_KEY", "key": SECRET}, headers=ADMIN_H
    )
    assert unknown.status_code == 400
    assert _put_builtin(client, key="sk 123 456").status_code == 400
    assert _put_builtin(client, base="ftp://x.example").status_code == 400
    assert _put_builtin(client, protocol="native").status_code == 400  # 原生协议要写适配名
    assert client.put(f"{URL}/custom/Bad_ID", json=KIMI, headers=ADMIN_H).status_code == 400
    no_base = {**KIMI, "api_base": ""}
    assert client.put(f"{URL}/custom/kimi", json=no_base, headers=ADMIN_H).status_code == 400
    clash = {**KIMI, "models": [{"model": "agent", "kind": "chat"}]}  # chat-agent 是分组名
    assert client.put(f"{URL}/custom/chat", json=clash, headers=ADMIN_H).status_code == 400
    dup = {**KIMI, "models": [KIMI["models"][0], KIMI["models"][0]]}
    assert client.put(f"{URL}/custom/kimi", json=dup, headers=ADMIN_H).status_code == 400


def test_private_base_blocked_in_production(
    client: TestClient, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "model_allow_private_base", False)
    for url in ("http://127.0.0.1:11434/v1", "http://169.254.169.254/latest", "http://10.0.0.8/v1"):
        r = client.put(f"{URL}/custom/ollama", json={**KIMI, "api_base": url}, headers=ADMIN_H)
        assert r.status_code == 400 and "MODEL_ALLOW_PRIVATE_BASE" in r.json()["message"]
    assert _put_builtin(client, base="http://127.0.0.1:8000/v1").status_code == 400
    monkeypatch.setattr(get_settings(), "model_allow_private_base", True)
    ok = client.put(
        f"{URL}/custom/ollama",
        json={**KIMI, "api_base": "http://127.0.0.1:11434/v1"},
        headers=ADMIN_H,
    )
    assert ok.status_code == 200 and ok.json()["data"]["allow_private_base"] is True


def test_custom_provider_lifecycle(client: TestClient, gateway: FakeGateway) -> None:
    data = client.put(f"{URL}/custom/kimi", json=KIMI, headers=ADMIN_H).json()["data"]
    kimi = data["custom"][0]
    assert (
        kimi["name"] == "Kimi" and kimi["has_key"] and kimi["tail"] == "6789" and kimi["available"]
    )
    assert [m["alias"] for m in kimi["models"]] == ["kimi-moonshot-v1-8k", "kimi-kimi-embed"]
    assert KIMI["key"] not in str(data)
    pushed = gateway.config["custom"][0]
    assert pushed["api_key"] == KIMI["key"] and pushed["models"][1]["capabilities"]["dims"] == 1024
    assert "kimi-moonshot-v1-8k" in {m["alias"] for m in data["models"]}
    # 改名、不带 key：保留原来的 Key
    renamed = client.put(
        f"{URL}/custom/kimi", json={**KIMI, "name": "月之暗面", "key": None}, headers=ADMIN_H
    )
    assert renamed.json()["data"]["custom"][0]["name"] == "月之暗面"
    assert gateway.config["custom"][0]["api_key"] == KIMI["key"]
    # 设为对话主用，删除厂商后分组里也去掉
    groups = {"chat": ["kimi-moonshot-v1-8k", "deepseek-chat"], "rerank": []}
    r = client.put(f"{URL}/groups", json=groups, headers=ADMIN_H).json()["data"]
    assert r["groups"]["chat-agent"] == ["kimi-moonshot-v1-8k", "deepseek-chat"]
    gone = client.delete(f"{URL}/custom/kimi", headers=ADMIN_H).json()["data"]
    assert gone["custom"] == [] and gateway.config["groups"]["chat-agent"] == ["deepseek-chat"]
    assert client.delete(f"{URL}/custom/kimi", headers=ADMIN_H).status_code == 404


def test_groups_validation(client: TestClient, gateway: FakeGateway) -> None:
    bad = client.put(f"{URL}/groups", json={"chat": ["embed-default"]}, headers=ADMIN_H)
    assert bad.status_code == 400
    unknown = client.put(f"{URL}/groups", json={"chat": ["nope"]}, headers=ADMIN_H)
    assert unknown.status_code == 400
    assert client.put(f"{URL}/groups", json={"chat": []}, headers=ADMIN_H).status_code == 400
    gateway.down = True
    down = client.put(f"{URL}/groups", json={"chat": ["deepseek-chat"]}, headers=ADMIN_H)
    assert down.status_code == 502


def test_probe_uses_typed_or_saved_key(client: TestClient, gateway: FakeGateway) -> None:
    body = {"var": "HUNYUAN_API_KEY", "key": "sk-wrong-key"}
    assert (
        client.post(f"{URL}/builtin/test", json=body, headers=ADMIN_H).json()["data"]["ok"] is False
    )
    _put_builtin(client, key=SECRET)
    saved = client.post(
        f"{URL}/builtin/test", json={"var": "HUNYUAN_API_KEY"}, headers=ADMIN_H
    ).json()
    assert saved["data"]["ok"] is True and gateway.tested[-1]["override"]["key"] == SECRET
    client.post(
        f"{URL}/builtin/test",
        json={"var": "DEEPSEEK_API_KEY", "base": "https://x.example/v1"},
        headers=ADMIN_H,
    )
    assert gateway.tested[-1]["override"] == {  # 没有网页上的 Key：由网关用 .env 的
        "key": "",
        "base": "https://x.example/v1",
        "protocol": "",
        "adapter": "",
    }
    # 自定义模型：没填 Key 用已保存的，返回检测到的能力
    client.put(f"{URL}/custom/kimi", json=KIMI, headers=ADMIN_H)
    test = {"api_base": KIMI["api_base"], "model": KIMI["models"][0]}
    r = client.post(f"{URL}/custom/kimi/test", json=test, headers=ADMIN_H).json()["data"]
    assert r["ok"] and r["capabilities"]["tools"] is True
    assert gateway.tested[-1]["provider"]["api_key"] == KIMI["key"]
    assert KIMI["key"] not in str(r)


def test_gateway_restart_is_resynced(client: TestClient, gateway: FakeGateway) -> None:
    _put_builtin(client, key=SECRET)
    client.put(f"{URL}/custom/kimi", json=KIMI, headers=ADMIN_H)
    gateway.config = {
        "version": "",
        "builtin": {},
        "custom": [],
        "groups": {},
    }  # 网关重启，内存里的配置没了
    svc.sync_once()
    assert gateway.config["builtin"]["HUNYUAN_API_KEY"]["key"] == SECRET
    assert gateway.config["custom"][0]["id"] == "kimi"
    pushes = gateway.pushes
    svc.sync_once()  # 版本一致：不重复推送
    assert gateway.pushes == pushes


def test_saved_while_gateway_down(client: TestClient, gateway: FakeGateway) -> None:
    gateway.down = True
    r = _put_builtin(client, key=SECRET)
    data = r.json()["data"]
    assert r.json()["code"] == 0 and data["gateway_ok"] is False
    assert _builtin(data, "HUNYUAN_API_KEY")["key_source"] == "web"
    gateway.down = False
    svc.sync_once()
    assert gateway.config["builtin"]["HUNYUAN_API_KEY"]["key"] == SECRET


def test_key_secret_rotation_and_broken_keys(
    client: TestClient, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "model_keys_secret", "")
    _put_builtin(client, key=SECRET)  # 用 JWT_SECRET 派生的密钥加密
    # 设置 MODEL_KEYS_SECRET 之后旧密文仍能解开，下次保存时换成新密钥
    monkeypatch.setattr(settings, "model_keys_secret", "model-keys-secret-" + "z" * 32)
    assert _builtin(_offline_status(), "HUNYUAN_API_KEY")["broken"] is False
    client.put(f"{URL}/custom/kimi", json=KIMI, headers=ADMIN_H)
    # 再换 JWT_SECRET：已经换成新密钥加密的不受影响
    monkeypatch.setattr(settings, "jwt_secret", "another-secret-" + "y" * 32)
    assert _builtin(_offline_status(), "HUNYUAN_API_KEY")["broken"] is False
    # 两个都换掉：解不开，提示重新填写
    monkeypatch.setattr(settings, "model_keys_secret", "third-secret-" + "w" * 32)
    status = _offline_status()
    assert _builtin(status, "HUNYUAN_API_KEY")["broken"] is True
    assert _builtin(status, "HUNYUAN_API_KEY")["key_source"] == "none"
    assert status["custom"][0]["broken"] is True


@pytest.fixture
def chunk() -> Iterator[uuid.UUID]:
    with session_scope() as db:
        row = KbChunk(
            scope="company",
            pack=None,
            doc_name="切换向量测试",
            section="一",
            content="测试内容",
            content_hash=uuid.uuid4().hex,
            embedding=[0.0] * get_settings().embedding_dims,
        )
        db.add(row)
        db.flush()
        cid = row.id
    yield cid
    with session_scope() as db:
        db.execute(delete(KbChunk).where(KbChunk.id == cid))


def _wait_job() -> None:
    for _ in range(100):
        if not svc._JOB:
            return
        time.sleep(0.05)
    raise AssertionError("reindex did not finish")


def test_switch_embedding_rebuilds_then_switches(
    client: TestClient, gateway: FakeGateway, chunk: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    only_mine = svc._load_chunks
    monkeypatch.setattr(svc, "_load_chunks", lambda db: [c for c in only_mine(db) if c[0] == chunk])
    dims = get_settings().embedding_dims
    calls: list[tuple[list[str], str | None]] = []

    def fake_embed(texts: list[str], *, model: str | None = None, **_: Any) -> list[list[float]]:
        calls.append((texts, model))
        return [[0.5] * dims for _ in texts]

    monkeypatch.setattr(llm_client, "embed_texts", fake_embed)
    client.put(f"{URL}/custom/kimi", json=KIMI, headers=ADMIN_H)
    same = client.post(f"{URL}/embedding", json={"alias": "embed-default"}, headers=ADMIN_H)
    assert same.status_code == 400  # 已经在用
    chat = client.post(f"{URL}/embedding", json={"alias": "kimi-moonshot-v1-8k"}, headers=ADMIN_H)
    assert chat.status_code == 400
    r = client.post(f"{URL}/embedding", json={"alias": "kimi-kimi-embed"}, headers=ADMIN_H)
    assert r.status_code == 200
    _wait_job()
    assert calls == [(["切换向量测试 > 一\n测试内容"], "kimi-kimi-embed")]
    with session_scope() as db:
        vec = db.scalar(select(KbChunk.embedding).where(KbChunk.id == chunk))
        assert vec is not None and float(vec[0]) == 0.5
    data = client.get(URL, headers=ADMIN_H).json()["data"]
    assert data["reindex"]["status"] == "done" and data["reindex"]["total"] == 1
    assert gateway.config["groups"]["embed"] == ["kimi-kimi-embed"]
    # 正在用的向量模型所在厂商不能删
    assert client.delete(f"{URL}/custom/kimi", headers=ADMIN_H).status_code == 400


def test_switch_embedding_failure_keeps_old_model(
    client: TestClient, gateway: FakeGateway, chunk: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    only_mine = svc._load_chunks
    monkeypatch.setattr(svc, "_load_chunks", lambda db: [c for c in only_mine(db) if c[0] == chunk])
    monkeypatch.setattr(llm_client, "embed_texts", lambda texts, **_: [[0.1] * 8 for _ in texts])
    client.put(f"{URL}/custom/kimi", json=KIMI, headers=ADMIN_H)
    client.post(f"{URL}/embedding", json={"alias": "kimi-kimi-embed"}, headers=ADMIN_H)
    _wait_job()
    data = client.get(URL, headers=ADMIN_H).json()["data"]
    assert data["reindex"]["status"] == "failed" and "8 维" in data["reindex"]["error"]
    assert data["groups"]["embed"] == ["embed-default"]
    with session_scope() as db:
        vec = db.scalar(select(KbChunk.embedding).where(KbChunk.id == chunk))
        assert vec is not None and float(vec[0]) == 0.0
