"""企业微信群机器人：地址校验与脱敏、权限、事务提交后才推送、事件开关、日报推送与提醒。

不访问真实的企业微信：用假的 httpx.post 记录请求。
"""

import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.common.db import session_scope
from app.crm.models import Integration
from app.crm.services import wecom_service
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.api.test_opportunities_api import new_opp

URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-0000-1111-2222"


class FakeWecom:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail = False

    def post(self, url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        self.sent.append({"url": url, **json})
        body = {"errcode": 93000, "errmsg": "invalid webhook url"} if self.fail else {"errcode": 0}
        return httpx.Response(200, json=body)

    def texts(self) -> list[str]:
        return [m["markdown"]["content"] for m in self.sent]


@pytest.fixture
def wecom(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> Iterator[FakeWecom]:
    fake = FakeWecom()
    monkeypatch.setattr(wecom_service.httpx, "post", fake.post)
    # 后台线程改成同步执行，便于断言
    monkeypatch.setattr(wecom_service._pool, "submit", lambda fn, *a: fn(*a))
    r = client.put("/api/integrations/wecom", json={"webhook_url": URL}, headers=ADMIN_H)
    assert r.json()["code"] == 0, r.text
    yield fake
    with session_scope() as db:
        db.execute(delete(Integration).where(Integration.kind == "wecom"))


def test_config_masks_url_and_validates(client: TestClient, wecom: FakeWecom) -> None:
    data = client.get("/api/integrations/wecom", headers=ADMIN_H).json()["data"]
    assert data["configured"] and data["source"] == "web"
    assert "test-0000" not in data["webhook_masked"] and data["webhook_masked"].endswith("2222")
    bad = {"webhook_url": "http://127.0.0.1:8000/internal"}
    assert client.put("/api/integrations/wecom", json=bad, headers=ADMIN_H).json()["code"] == 40001
    assert client.get("/api/integrations/wecom", headers=MANAGER_H).json()["code"] == 40301
    flags = client.get("/api/integrations/flags", headers=SALES_H).json()["data"]
    assert flags["deal_won"] is True


def test_send_test_and_record_failure(client: TestClient, wecom: FakeWecom) -> None:
    r = client.post("/api/integrations/wecom/test", headers=ADMIN_H).json()["data"]
    assert r["ok"] and "测试消息" in wecom.texts()[0]
    wecom.fail = True
    r = client.post("/api/integrations/wecom/test", headers=ADMIN_H).json()["data"]
    assert not r["ok"] and "invalid webhook url" in r["error"]
    recent = client.get("/api/integrations/wecom", headers=ADMIN_H).json()["data"]["recent"]
    assert [p["ok"] for p in recent[:2]] == [False, True]


def test_deal_won_pushed_after_commit(
    client: TestClient, tracker: Tracker, wecom: FakeWecom
) -> None:
    opp = new_opp(client, tracker)
    r = client.patch(
        f"/api/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=SALES_H
    )
    assert r.json()["code"] == 0
    assert any("赢单喜报" in t and opp["name"] in t for t in wecom.texts())


def test_rolled_back_change_is_not_pushed(wecom: FakeWecom) -> None:
    with pytest.raises(RuntimeError), session_scope() as db:
        wecom_service.queue(db, "deal_won", "x", "不应发送")
        raise RuntimeError("rollback")
    assert wecom.sent == []


def test_disabled_event_not_pushed(client: TestClient, tracker: Tracker, wecom: FakeWecom) -> None:
    body = {"enabled": True, "events": ["approval_pending"]}
    client.put("/api/integrations/wecom", json=body, headers=ADMIN_H)
    opp = new_opp(client, tracker)
    client.patch(f"/api/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=SALES_H)
    assert wecom.sent == []
    assert (
        client.get("/api/integrations/flags", headers=SALES_H).json()["data"]["deal_won"] is False
    )


def test_report_push_and_remind(client: TestClient, wecom: FakeWecom) -> None:
    body = {"content": f"本周汇总-{uuid.uuid4().hex[:6]}"}
    r = client.post("/api/reports/team/push", json=body, headers=MANAGER_H).json()
    assert r["code"] == 0 and r["data"]["ok"]
    assert body["content"] in wecom.texts()[-1]
    assert client.post("/api/reports/team/push", json=body, headers=SALES_H).json()["code"] == 40301
    r = client.post("/api/reports/team/remind", json={}, headers=MANAGER_H).json()
    if r["code"] == 0:  # 本队可能都已提交（其他用例产生的数据），此时返回 40001
        assert "日报提醒" in wecom.texts()[-1]
    else:
        assert r["code"] == 40001


def test_push_requires_config(client: TestClient) -> None:
    with session_scope() as db:
        db.execute(delete(Integration).where(Integration.kind == "wecom"))
    r = client.post("/api/reports/team/push", json={"content": "x"}, headers=MANAGER_H).json()
    assert r["code"] == 40001 and "消息推送" in r["message"]
