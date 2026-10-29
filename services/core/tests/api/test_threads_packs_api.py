"""会话列表 / 会话历史、行业包详情接口（需要数据库）。"""

import threading
import uuid
from collections.abc import Iterator
from typing import Any

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
    assert set(first) == {"thread_id", "title", "updated_at", "opportunity_id", "running"}
    assert first["running"] is False
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
    assert body["data"] == {
        "thread_id": threads[0],
        "messages": [],
        "pending": None,
        "running": None,
        "opportunity_id": None,
    }


@pytest.mark.parametrize("pack_id", ["llm_deploy", "it_office"])
def test_pack_detail_all_roles(client: TestClient, pack_id: str) -> None:
    for headers in (SALES_H, MANAGER_H, ADMIN_H):
        body = client.get(f"/api/packs/{pack_id}", headers=headers).json()
        assert body["code"] == 0
        data = body["data"]
        assert data["id"] == pack_id and data["catalog"] and data["knowledge"]
        assert data["rules"]["margin"]["floor_rate"] == 0.25
        item = data["catalog"][0]
        assert set(item) == {
            *("sku", "name", "category", "unit", "cost", "price", "specs"),
            *("default_cost", "default_price", "overridden"),
        }
        assert isinstance(item["price"], int)


def test_pack_detail_not_installed(client: TestClient) -> None:
    assert client.get("/api/packs/no_such_pack", headers=SALES_H).json()["code"] == 40401


def test_pack_knowledge_marks_indexed_formats(client: TestClient) -> None:
    """知识库列表标出哪些文件会入库：md / pdf / xlsx 入库，models.json 是配置数据不入库。"""
    docs = client.get("/api/packs/llm_deploy", headers=ADMIN_H).json()["data"]["knowledge"]
    by_name = {d["doc_name"]: d for d in docs}
    assert by_name["GPU与整机参数表.xlsx"] == {
        **by_name["GPU与整机参数表.xlsx"],
        "format": "xlsx",
        "indexed": True,
    }
    assert by_name["显存估算参考表.md"]["indexed"] is True
    assert by_name["models.json"]["indexed"] is False


def test_rename_and_delete_thread(client: TestClient, threads: list[str]) -> None:
    """会话改名、删除（审查 v6 #14）；别人的会话 404。"""
    url = f"/api/agent/threads/{threads[0]}"
    r = client.patch(url, json={"title": "  明理律所 · 标准版  "}, headers=SALES_H)
    assert r.json()["data"]["title"] == "明理律所 · 标准版"
    assert client.patch(url, json={"title": "x"}, headers=SALES2_H).status_code == 404
    assert client.delete(url, headers=SALES2_H).status_code == 404
    assert client.delete(url, headers=SALES_H).json()["code"] == 0
    listed = client.get("/api/agent/threads", headers=SALES_H).json()["data"]["items"]
    assert threads[0] not in {t["thread_id"] for t in listed}
    assert client.delete(url, headers=SALES_H).status_code == 404


def test_running_thread_messages_stream_and_stop(
    client: TestClient, threads: list[str], sse_parser: Any
) -> None:
    """切走再回来：messages 返回本轮开始前的内容 + running，/stream 从头重放本轮。"""
    from app.agent.history import HistoryMessage, ThreadMessages
    from app.agent.runs import Run, registry

    tid, gate = threads[0], threading.Event()

    def events() -> Iterator[dict[str, Any]]:
        yield {"event": "message.delta", "data": {"text": "正在出方案"}}
        gate.wait(5)
        yield {"event": "done", "data": {"thread_id": tid}}

    base = ThreadMessages(
        thread_id=tid, messages=[HistoryMessage(role="user", text="上一轮的问题")]
    )
    run = registry.start(Run(tid, str(SALES.id), "chat", "这一轮的问题", base), events())
    try:
        body = client.get(f"/api/agent/threads/{tid}/messages", headers=SALES_H).json()["data"]
        assert body["running"] == {"kind": "chat", "input": "这一轮的问题"}
        assert [m["text"] for m in body["messages"]] == ["上一轮的问题"]
        items = client.get("/api/agent/threads?limit=100", headers=SALES_H).json()["data"]["items"]
        assert next(t for t in items if t["thread_id"] == tid)["running"] is True
        # 别人不能订阅 / 停止
        other = client.get(f"/api/agent/threads/{tid}/stream", headers=SALES2_H)
        assert other.json()["code"] == 40401
        again = {"thread_id": tid, "message": "并发再发一条"}
        assert client.post("/api/agent/chat", json=again, headers=SALES_H).json()["code"] == 40901
        assert client.post(f"/api/agent/threads/{tid}/stop", headers=SALES_H).json()["code"] == 0
    finally:
        gate.set()
    events_seen = sse_parser(client.get(f"/api/agent/threads/{tid}/stream", headers=SALES_H).text)
    assert events_seen[0] == ("message.delta", {"text": "正在出方案"})
    assert events_seen[-1][0] == "done" and run.done
    body = client.get(f"/api/agent/threads/{tid}/messages", headers=SALES_H).json()["data"]
    assert body["running"] is None
    missing = client.post(f"/api/agent/threads/{threads[1]}/stop", headers=SALES_H)
    assert missing.json()["code"] == 40401
