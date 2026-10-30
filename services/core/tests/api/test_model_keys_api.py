"""模型厂商 Key：管理员网页填写、加密存库、推送网关、不回显、换 JWT_SECRET 后提示重填。"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.common.config import get_settings
from app.common.db import session_scope
from app.crm.models import AuditLog, Integration
from app.crm.services import model_keys_service
from app.llm import client as llm_client
from tests.api.conftest import ADMIN_H, MANAGER_H

URL = "/api/integrations/model-keys"
SECRET = "sk-test-0123456789abcd"


class FakeGateway:
    """模拟网关的 /v1/admin/*：记录推送内容，按推送的 Key 计算可用性。"""

    def __init__(self) -> None:
        self.version = ""
        self.keys: dict[str, str] = {}
        self.env = {"DEEPSEEK_API_KEY"}
        self.down = False
        self.pushes = 0
        self.tested: list[dict[str, Any]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict:
        if self.down:
            raise model_keys_service.BizError(model_keys_service.ErrorCode.UPSTREAM, "down")
        if path == "keys":
            self.keys, self.version = dict(body["keys"]), body["version"]
            self.pushes += 1
        if path == "keys/test":
            self.tested.append(body)
            return {"ok": body["key"] != "sk-wrong-key", "model": "m", "error": None}
        return {
            "version": self.version,
            "providers": [
                {
                    "var": var,
                    "models": [var.lower()],
                    "env_configured": var in self.env,
                    "available": var in self.keys or var in self.env,
                }
                for var in ("HUNYUAN_API_KEY", "DEEPSEEK_API_KEY")
            ],
        }


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGateway]:
    fake = FakeGateway()
    monkeypatch.setattr(llm_client, "gateway_admin", fake)
    yield fake
    with session_scope() as db:
        db.execute(delete(Integration).where(Integration.kind == model_keys_service.KIND))


def _offline_status() -> dict:
    with session_scope() as db:
        saved = model_keys_service._saved(db)
    return model_keys_service._status(saved, None).model_dump()


def _provider(data: dict, var: str) -> dict:
    return next(p for p in data["providers"] if p["var"] == var)


def test_only_admin(client: TestClient, gateway: FakeGateway) -> None:
    assert client.get(URL, headers=MANAGER_H).status_code == 403
    body = {"var": "HUNYUAN_API_KEY", "key": SECRET}
    assert client.put(URL, json=body, headers=MANAGER_H).status_code == 403


def test_save_encrypts_pushes_and_masks(client: TestClient, gateway: FakeGateway) -> None:
    before = client.get(URL, headers=ADMIN_H).json()["data"]
    assert before["gateway_ok"] is True
    assert _provider(before, "HUNYUAN_API_KEY")["source"] == "none"
    assert _provider(before, "DEEPSEEK_API_KEY")["source"] == "env"
    r = client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": f"  {SECRET} "}, headers=ADMIN_H)
    data = r.json()["data"]
    hunyuan = _provider(data, "HUNYUAN_API_KEY")
    assert hunyuan["source"] == "web" and hunyuan["tail"] == "abcd" and hunyuan["available"]
    assert hunyuan["label"] == "腾讯混元" and hunyuan["saved_by"] == "周敏"
    assert SECRET not in r.text
    assert gateway.keys == {"HUNYUAN_API_KEY": SECRET} and gateway.version
    with session_scope() as db:
        row = db.scalar(select(Integration).where(Integration.kind == "model_keys"))
        assert row is not None and SECRET not in str(row.config)  # 库里是密文
        log = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "settings.model_key")
            .order_by(AuditLog.created_at.desc())
        )
        assert log is not None and SECRET not in str(log.__dict__)
    # 清除：回到 .env（这里没有）
    cleared = client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": ""}, headers=ADMIN_H)
    assert _provider(cleared.json()["data"], "HUNYUAN_API_KEY")["source"] == "none"
    assert gateway.keys == {} and gateway.version == ""


def test_rejects_bad_input(client: TestClient, gateway: FakeGateway) -> None:
    unknown = client.put(URL, json={"var": "OPENAI_API_KEY", "key": SECRET}, headers=ADMIN_H)
    assert unknown.status_code == 400
    spaced = client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": "sk 123 456"}, headers=ADMIN_H)
    assert spaced.status_code == 400


def test_gateway_restart_is_resynced(client: TestClient, gateway: FakeGateway) -> None:
    client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": SECRET}, headers=ADMIN_H)
    gateway.keys, gateway.version = {}, ""  # 网关重启，内存里的 Key 没了
    model_keys_service.sync_once()
    assert gateway.keys == {"HUNYUAN_API_KEY": SECRET}
    pushes = gateway.pushes
    model_keys_service.sync_once()  # 版本一致：不重复推送
    assert gateway.pushes == pushes


def test_saved_while_gateway_down(client: TestClient, gateway: FakeGateway) -> None:
    gateway.down = True
    r = client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": SECRET}, headers=ADMIN_H)
    data = r.json()["data"]
    assert r.json()["code"] == 0 and data["gateway_ok"] is False
    assert _provider(data, "HUNYUAN_API_KEY")["source"] == "web"
    gateway.down = False
    model_keys_service.sync_once()
    assert gateway.keys == {"HUNYUAN_API_KEY": SECRET}


def test_changed_jwt_secret_marks_key_broken(
    client: TestClient, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": SECRET}, headers=ADMIN_H)
    assert _provider(_offline_status(), "HUNYUAN_API_KEY")["broken"] is False
    monkeypatch.setattr(get_settings(), "jwt_secret", "another-secret-" + "y" * 32)
    broken = _provider(_offline_status(), "HUNYUAN_API_KEY")
    assert broken["broken"] is True and broken["source"] == "none"


def test_probe_uses_typed_or_saved_key(client: TestClient, gateway: FakeGateway) -> None:
    typed = client.post(
        f"{URL}/test", json={"var": "HUNYUAN_API_KEY", "key": "sk-wrong-key"}, headers=ADMIN_H
    ).json()["data"]
    assert typed["ok"] is False
    client.put(URL, json={"var": "HUNYUAN_API_KEY", "key": SECRET}, headers=ADMIN_H)
    saved = client.post(f"{URL}/test", json={"var": "HUNYUAN_API_KEY"}, headers=ADMIN_H).json()
    assert saved["data"]["ok"] is True and gateway.tested[-1]["key"] == SECRET
    client.post(f"{URL}/test", json={"var": "DEEPSEEK_API_KEY"}, headers=ADMIN_H)
    assert gateway.tested[-1]["key"] is None  # 没有网页上的：由网关用 .env 的
