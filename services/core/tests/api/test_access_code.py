"""访问口令：配置 ACCESS_CODE 后登录必须带口令；已登录切换账户不用；错误过多暂时锁定。"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.common.config import get_settings
from app.crm.services import auth_service

URL = "/api/auth/mock-login"


@pytest.fixture
def code(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setattr(get_settings(), "access_code", "salespilot-2026")
    auth_service._failures.clear()
    yield "salespilot-2026"
    auth_service._failures.clear()


def test_options_without_code(client: TestClient) -> None:
    r = client.get("/api/auth/options").json()
    assert r["data"] == {"access_code_required": False, "demo_login": True}
    assert client.post(URL, json={"role": "sales"}).json()["code"] == 0


def test_login_requires_code(client: TestClient, code: str) -> None:
    assert client.get("/api/auth/options").json()["data"]["access_code_required"] is True
    missing = client.post(URL, json={"role": "sales"})
    assert missing.status_code == 401
    assert missing.json()["code"] == 40101 and missing.json()["message"] == "请输入访问口令"
    wrong = client.post(URL, json={"role": "sales", "access_code": "guess"}).json()
    assert wrong["code"] == 40101 and wrong["data"]["rule"] == "access_code"
    good = client.post(URL, json={"role": "sales", "access_code": code}).json()
    assert good["code"] == 0
    # 已登录切换到主管：带当前 token，不用口令
    token = good["data"]["token"]
    switch = client.post(
        URL, json={"role": "manager"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert switch.json()["data"]["user"]["role"] == "manager"
    forged = client.post(URL, json={"role": "admin"}, headers={"Authorization": "Bearer x.y.z"})
    assert forged.json()["code"] == 40101


def test_too_many_wrong_codes_locks(client: TestClient, code: str) -> None:
    for _ in range(auth_service.MAX_FAILURES):
        assert (
            client.post(URL, json={"role": "sales", "access_code": "bad"}).json()["code"] == 40101
        )
    locked = client.post(URL, json={"role": "sales", "access_code": code})
    assert locked.status_code == 429 and locked.json()["code"] == 42901
