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


def _test_database_url() -> str:
    """测试专用库：默认在 DATABASE_URL 的库名后加 _test（crm → crm_test）。

    曾经的问题：测试、接口端到端测试、浏览器测试共用开发库，互相留下数据，
    导致按金额精确断言的用例时好时坏。现在测试库每次运行前都重建演示数据，结果可复现。
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = os.environ.get("DATABASE_URL", "postgresql+psycopg://crm:crm@localhost:5432/crm")
    head, _, name = base.rpartition("/")
    name = name.split("?")[0]
    return base if name.endswith("_test") else f"{head}/{name}_test"


os.environ["DATABASE_URL"] = _test_database_url()
os.environ.setdefault("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), ".uploads"))

from fastapi.testclient import TestClient

from app.agent.tools.base import ToolContext
from app.common.auth import Role, issue_token
from app.common.db import check_db
from app.crm.schemas.quote import QuoteOut
from app.crm.services.demo import DEMO_USERS
from app.main import app
from app.packs.base import SolutionTier


def _ensure_test_database() -> bool:
    """测试库不存在就创建；连不上 Postgres 服务器时返回 False（需要数据库的用例 skip）。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL"])
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with server.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except Exception:
        return False
    finally:
        server.dispose()
    return True


def _migrate_and_seed() -> None:
    """迁移到最新，并清空后重新导入演示数据，保证每次测试从同一个状态开始。"""
    from alembic import command
    from alembic.config import Config

    from app.common.db import session_scope
    from seed.__main__ import reset_business_data, seed_crm, seed_org
    from seed.business import seed_business

    root = os.path.dirname(os.path.dirname(__file__))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "migrations"))
    command.upgrade(cfg, "head")
    with session_scope() as db:
        reset_business_data(db)
        seed_org(db)
        seed_crm(db)
        db.flush()
        seed_business(db)


@pytest.fixture(scope="session")
def db_available() -> bool:
    if not _ensure_test_database() or not check_db():
        return False
    _migrate_and_seed()
    return True


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
    customer_id: Any = None,
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
