"""DbDep 必须在响应发出之前提交事务（回归：上传票据后立刻刷新详情，偶发读到提交前的数据）。"""

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.db import get_db
from app.crm.routers.deps import DbDep


def _app_recording(events: list[str]) -> ASGIApp:
    app = FastAPI()

    def fake_db() -> Iterator[object]:
        yield object()
        events.append("commit")

    app.dependency_overrides[get_db] = fake_db

    @app.post("/write")
    def write(db: DbDep) -> dict[str, bool]:
        events.append("handler")
        return {"ok": True}

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                events.append("response_sent")
            await send(message)

        await app(scope, receive, wrapped)

    return middleware


def test_db_session_commits_before_response_is_sent() -> None:
    events: list[str] = []
    with TestClient(_app_recording(events)) as client:
        assert client.post("/write").status_code == 200
    assert events == ["handler", "commit", "response_sent"]
