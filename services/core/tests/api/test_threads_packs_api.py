"""会话列表 / 会话历史、行业包详情接口（需要数据库）。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.agent.threads import upsert_thread
from app.common.auth import CurrentUser, Role
from app.common.db import session_scope
from app.common.errors import BizError
from app.crm.models import AgentThread
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, token_header

SALES = DEMO_USERS[Role.SALES]


@pytest.fixture
def threads() -> Iterator[list[str]]:
    """为销售张晨建两条会话、王磊一条，结束后删除。"""
    ids = [f"test-{uuid.uuid4().hex[:12]}" for _ in range(3)]
    with session_scope() as db:
        upsert_thread(db, SALES, ids[0], "第一条会话：明理律所 Qwen3-32B 私有化部署方案，50 人并发")
        upsert_thread(db, EXTRA_SALES, ids[2], "王磊的会话")
    with session_scope() as db:
        upsert_thread(db, SALES, ids[1], "第二条会话")
    yield ids
    with session_scope() as db:
        db.execute(delete(AgentThread).where(AgentThread.thread_id.in_(ids)))


def test_list_only_own_threads(client: TestClient, threads: list[str]) -> None:
    data = client.get("/api/agent/threads?limit=100", headers=SALES_H).json()["data"]
    ids = [t["thread_id"] for t in data["items"]]
    assert threads[0] in ids and threads[1] in ids and threads[2] not in ids
    assert ids.index(threads[1]) < ids.index(threads[0])  # updated_at 倒序
    first = next(t for t in data["items"] if t["thread_id"] == threads[0])
    assert first["title"].startswith("第一条会话") and len(first["title"]) == 30
    assert set(first) == {"thread_id", "title", "updated_at", "opportunity_id"}
    assert data["total"] >= 2


def test_upsert_keeps_title_and_bumps_order(client: TestClient, threads: list[str]) -> None:
    with session_scope() as db:
        upsert_thread(db, SALES, threads[0], "后续消息不改标题")
    items = client.get("/api/agent/threads", headers=SALES_H).json()["data"]["items"]
    ids = [t["thread_id"] for t in items]
    assert ids.index(threads[0]) < ids.index(threads[1])
    assert items[ids.index(threads[0])]["title"].startswith("第一条会话")


def test_upsert_other_users_thread_rejected(threads: list[str]) -> None:
    with pytest.raises(BizError) as exc, session_scope() as db:
        upsert_thread(db, SALES, threads[2], "抢别人的会话")
    assert exc.value.code == 40401


def test_list_empty_for_new_user(client: TestClient) -> None:
    fresh = CurrentUser(id=uuid.uuid4(), name="新人", role=Role.SALES)
    body = client.get("/api/agent/threads", headers=token_header(fresh)).json()
    assert body["code"] == 0 and body["data"] == {"items": [], "total": 0}


def test_list_limit_validation(client: TestClient) -> None:
    assert client.get("/api/agent/threads?limit=0", headers=SALES_H).json()["code"] == 40001


def test_messages_cross_user_404(client: TestClient, threads: list[str]) -> None:
    for headers in (SALES2_H, MANAGER_H, ADMIN_H):
        resp = client.get(f"/api/agent/threads/{threads[0]}/messages", headers=headers)
        assert resp.json()["code"] == 40401


def test_messages_empty_thread(client: TestClient, threads: list[str]) -> None:
    body = client.get(f"/api/agent/threads/{threads[0]}/messages", headers=SALES_H).json()
    assert body["code"] == 0
    assert body["data"] == {"thread_id": threads[0], "messages": [], "pending": None}


@pytest.mark.parametrize("pack_id", ["llm_deploy", "it_office"])
def test_pack_detail_all_roles(client: TestClient, pack_id: str) -> None:
    for headers in (SALES_H, MANAGER_H, ADMIN_H):
        body = client.get(f"/api/packs/{pack_id}", headers=headers).json()
        assert body["code"] == 0
        data = body["data"]
        assert data["id"] == pack_id and data["catalog"] and data["knowledge"]
        assert data["rules"]["margin"]["floor_rate"] == 0.25
        item = data["catalog"][0]
        assert set(item) == {"sku", "name", "category", "unit", "cost", "price", "specs"}
        assert isinstance(item["price"], int)


def test_pack_detail_not_installed(client: TestClient) -> None:
    assert client.get("/api/packs/no_such_pack", headers=SALES_H).json()["code"] == 40401
