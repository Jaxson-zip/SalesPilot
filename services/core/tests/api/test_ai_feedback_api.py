"""AI 回复的点赞 / 点踩：本人评价、改评价、取消；主管看本团队、管理员看全部「没帮助」。"""

import uuid

from fastapi.testclient import TestClient

from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H


def rate(client: TestClient, body: dict, headers: dict[str, str] = SALES_H) -> dict:
    return client.post("/api/ai-feedback", json=body, headers=headers).json()


def test_rate_change_cancel_and_review(client: TestClient) -> None:
    tid = f"test-{uuid.uuid4().hex}"
    base = {"thread_id": tid, "message_index": 0, "question": "提成怎么算", "answer": "按毛利分档"}
    assert rate(client, {**base, "rating": "up"})["data"]["rating"] == "up"
    # 改成没帮助，带原因（同一条回复只有一行）
    down = rate(client, {**base, "rating": "down", "comment": " 没说低毛利怎么算 "})["data"]
    assert down == {"message_index": 0, "rating": "down", "comment": "没说低毛利怎么算"}
    rate(client, {**base, "message_index": 1, "rating": "up"})
    mine = client.get(f"/api/ai-feedback/thread/{tid}", headers=SALES_H).json()["data"]
    assert sorted((r["message_index"], r["rating"]) for r in mine) == [(0, "down"), (1, "up")]

    # 主管（同团队）和管理员能看到没帮助的回复；销售不能看
    for h in (MANAGER_H, ADMIN_H):
        items = client.get("/api/ai-feedback?rating=down", headers=h).json()["data"]
        hit = next(i for i in items if i["question"] == "提成怎么算" and i["comment"])
        assert hit["user_name"] == "张晨" and hit["answer"] == "按毛利分档"
    assert client.get("/api/ai-feedback", headers=SALES_H).json()["code"] == 40301

    # 再点一次取消
    for i in (0, 1):
        assert rate(client, {**base, "message_index": i, "rating": None})["data"] is None
    assert client.get(f"/api/ai-feedback/thread/{tid}", headers=SALES_H).json()["data"] == []


def test_rate_validation(client: TestClient) -> None:
    body = {"thread_id": "t", "message_index": -1, "rating": "up"}
    assert rate(client, body)["code"] == 40001
    assert rate(client, {**body, "message_index": 0, "rating": "meh"})["code"] == 40001
