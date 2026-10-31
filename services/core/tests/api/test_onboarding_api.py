"""新手上手清单（接口契约 §36）：按角色给步骤，做没做完按真实数据判断。"""

from fastapi.testclient import TestClient

from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.api.test_quote_share_api import _approved, _share
from tests.api.test_solo_mode_api import _set_solo


def _keys(client: TestClient, headers: dict[str, str]) -> dict[str, bool]:
    data = client.get("/api/onboarding", headers=headers).json()["data"]
    assert data["total"] == len(data["steps"]) and data["done"] == sum(
        s["done"] for s in data["steps"]
    )
    return {s["key"]: s["done"] for s in data["steps"]}


def test_steps_by_role(client: TestClient) -> None:
    assert list(_keys(client, SALES_H)) == ["customer", "followup", "solution", "share"]
    assert list(_keys(client, MANAGER_H)) == ["customer", "followup", "solution", "share"]
    assert list(_keys(client, ADMIN_H)) == ["model", "pricing"]  # 管理员不做业务


def test_solo_manager_also_configures(client: TestClient) -> None:
    _set_solo(client, True)
    try:
        assert list(_keys(client, MANAGER_H))[:2] == ["model", "pricing"]
    finally:
        _set_solo(client, None)


def test_share_step_done_after_sharing(client: TestClient, tracker: Tracker) -> None:
    assert _keys(client, SALES_H)["customer"] is True  # 演示数据里张晨有客户
    qid = _approved(client, tracker)
    assert _share(client, qid)["code"] == 0
    assert _keys(client, SALES_H)["share"] is True


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/onboarding").json()["code"] == 40101
