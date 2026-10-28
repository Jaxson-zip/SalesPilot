"""竞品战卡：内置示例、搜索（客户原话）、管理员维护、商机标注与战绩、AI 工具。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.agent.tools import TOOLS, ToolContext
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Competitor
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.api.test_opportunities_api import new_opp


@pytest.fixture
def card(client: TestClient) -> Iterator[dict]:
    body = {
        "name": f"测试竞品-{uuid.uuid4().hex[:6]}",
        "aliases": ["测试厂商"],
        "summary": "测试用",
        "strengths": ["便宜", " "],
        "weaknesses": ["交付慢"],
        "win_tactics": ["算总成本"],
        "objections": [{"say": "他们报价低一半", "respond": "先看三年总成本"}],
    }
    r = client.post("/api/competitors", json=body, headers=ADMIN_H)
    assert r.json()["code"] == 0, r.text
    data = r.json()["data"]
    yield data
    with session_scope() as db:
        db.execute(delete(Competitor).where(Competitor.id == uuid.UUID(data["id"])))


def test_builtin_samples_and_search(client: TestClient) -> None:
    all_cards = client.get("/api/competitors", headers=SALES_H).json()["data"]
    names = {c["name"] for c in all_cards}
    assert {"公有云大模型 API", "大模型一体机厂商", "客户自建（开源 + 自有团队）"} <= names
    # 按客户原话搜：常见说法里有「便宜」
    hits = client.get("/api/competitors", params={"q": "按量付费"}, headers=SALES_H).json()
    assert [c["name"] for c in hits["data"]] == ["公有云大模型 API"]


def test_admin_maintains_cards(client: TestClient, card: dict) -> None:
    assert card["strengths"] == ["便宜"]  # 空行去掉
    body = {**card, "summary": "改过", "objections": card["objections"]}
    body.pop("id")
    body.pop("stats")
    body.pop("updated_by")
    r = client.put(f"/api/competitors/{card['id']}", json=body, headers=ADMIN_H)
    assert r.json()["data"]["summary"] == "改过"
    assert (
        client.put(f"/api/competitors/{card['id']}", json=body, headers=SALES_H).json()["code"]
        == 40301
    )
    dup = client.post("/api/competitors", json=body, headers=ADMIN_H).json()
    assert dup["code"] == 40901


def test_opportunity_competitors_and_stats(
    client: TestClient, tracker: Tracker, card: dict
) -> None:
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}/competitors"
    r = client.put(url, json={"ids": [card["id"]]}, headers=SALES_H)
    assert [c["name"] for c in r.json()["data"]] == [card["name"]]
    assert client.put(url, json={"ids": [card["id"]]}, headers=MANAGER_H).json()["code"] == 40301
    assert client.get(url, headers=MANAGER_H).json()["data"][0]["id"] == card["id"]
    # 输单 → 战绩里出现输单原因
    lost = {"stage": "lost", "lost_reason": "选择了竞品：报价低一半"}
    client.patch(f"/api/opportunities/{opp['id']}/stage", json=lost, headers=SALES_H)
    stats = next(
        c
        for c in client.get("/api/competitors", headers=SALES_H).json()["data"]
        if c["id"] == card["id"]
    )["stats"]
    assert stats["lost"] == 1 and stats["lost_reasons"] == ["选择了竞品：报价低一半"]


def test_delete_is_soft(client: TestClient, tracker: Tracker, card: dict) -> None:
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}/competitors"
    client.put(url, json={"ids": [card["id"]]}, headers=SALES_H)
    assert client.delete(f"/api/competitors/{card['id']}", headers=ADMIN_H).json()["code"] == 0
    names = {c["name"] for c in client.get("/api/competitors", headers=SALES_H).json()["data"]}
    assert card["name"] not in names
    assert client.get(url, headers=SALES_H).json()["data"] == []


def test_battlecard_tool_matches_customer_words() -> None:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope)
    spec = TOOLS["get_battlecard"]
    result = spec.func(ctx, spec.args_model(keyword="客户说他们 IT 想自己搭"))
    assert result.ok and result.data[0]["name"] == "客户自建（开源 + 自有团队）"
    assert result.data[0]["objections"]
