"""测试公共夹具。测试不依赖外网和真实 Key；需要数据库的用例在连不上时 skip。"""

import contextlib
import json
import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-only-32bytes!")
os.environ.setdefault("LLM_GATEWAY_BASE", "http://127.0.0.1:9/v1")  # 不可达，防止误调外网

from fastapi.testclient import TestClient

from app.agent.tools.base import ToolContext
from app.common.auth import Role, issue_token
from app.common.db import check_db
from app.crm.schemas.quote import QuoteOut
from app.crm.services.demo import DEMO_USERS
from app.main import app
from app.packs.base import SolutionTier


@pytest.fixture(scope="session")
def db_available() -> bool:
    return check_db()


@pytest.fixture
def client() -> TestClient:
    # 不进入 with 块：不运行 lifespan，checkpointer 懒加载为内存实现
    return TestClient(app)


def auth_header(role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(DEMO_USERS[role])}"}


@pytest.fixture
def null_session() -> Any:
    return lambda: contextlib.nullcontext(None)


@pytest.fixture
def tool_ctx(null_session: Any) -> ToolContext:
    return ToolContext(user=DEMO_USERS[Role.SALES], session=null_session, thread_id="t-test")


def fake_create_from_tier(
    db: Any,
    user: Any,
    *,
    pack: str,
    tier: SolutionTier,
    opportunity_id: Any,
    idempotency_key: str,
) -> QuoteOut:
    return QuoteOut(
        id=uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key),
        code="Q-2026-001",
        opportunity_id=opportunity_id,
        pack=pack,
        tier=tier.tier,
        status="draft",
        total_cost=tier.total_cost,
        total_price=tier.total_price,
        margin_rate=tier.margin_rate,
    )


@pytest.fixture
def fake_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.crm.services import quote_service

    monkeypatch.setattr(quote_service, "create_from_tier", fake_create_from_tier)


def parse_sse(text: str) -> list[tuple[str, Any]]:
    """把 SSE 响应体解析为 [(event, data)]。"""
    events: list[tuple[str, Any]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = None, []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if name:
            events.append((name, json.loads("\n".join(data)) if data else None))
    return events


@pytest.fixture
def sse_parser() -> Iterator[Any]:
    yield parse_sse
