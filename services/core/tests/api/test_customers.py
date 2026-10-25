"""客户接口：需要已迁移并导入演示数据的 Postgres，连不上时自动 skip。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect

from app.common.auth import Role
from app.common.db import get_engine, session_scope
from app.crm.models import Activity, Customer
from seed.data import C_MINGLI, C_PC3H
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def require_seeded_db(db_available: bool) -> None:
    if not db_available:
        pytest.skip("DATABASE_URL 连不上，跳过需要数据库的用例")
    if not inspect(get_engine()).has_table("customers"):
        pytest.skip("数据库未迁移（先执行 alembic upgrade head && python -m seed）")
    with session_scope() as db:
        if db.get(Customer, C_MINGLI) is None:
            pytest.skip("缺少演示数据（先执行 python -m seed）")


def names(client: TestClient, role: Role, query: str = "") -> set[str]:
    r = client.get(f"/api/customers{query}", headers=auth_header(role))
    assert r.status_code == 200, r.text
    return {item["name"] for item in r.json()["data"]["items"]}


def test_sales_sees_only_own(client: TestClient) -> None:
    got = names(client, Role.SALES)
    assert "深圳明理律师事务所" in got and "鹏城第三人民医院" not in got


def test_manager_sees_team(client: TestClient) -> None:
    assert "鹏城第三人民医院" in names(client, Role.MANAGER, "?view=team")


def test_list_fields_and_amount(client: TestClient) -> None:
    r = client.get("/api/customers?q=明理", headers=auth_header(Role.SALES))
    item = r.json()["data"]["items"][0]
    assert set(item) == {
        "id",
        "name",
        "industry",
        "level",
        "owner",
        "website",
        "opportunity_amount",
        "last_followup_at",
    }
    assert item["opportunity_amount"] == 37_200_000 and item["owner"]["name"] == "张晨"


def test_pagination(client: TestClient) -> None:
    r = client.get("/api/customers?page=1&page_size=2", headers=auth_header(Role.ADMIN))
    data = r.json()["data"]
    assert len(data["items"]) == 2 and data["total"] >= 5


def test_detail_forbidden_returns_404(client: TestClient) -> None:
    r = client.get(f"/api/customers/{C_PC3H}", headers=auth_header(Role.SALES))
    assert r.status_code == 404 and r.json()["code"] == 40401
    assert (
        client.get(f"/api/customers/{C_PC3H}", headers=auth_header(Role.MANAGER)).json()["code"]
        == 0
    )


@pytest.fixture
def temp_name() -> Iterator[str]:
    name = f"测试客户-{uuid.uuid4().hex[:6]}"
    yield name
    with session_scope() as db:
        ids = [c.id for c in db.query(Customer).filter(Customer.name == name)]
        db.execute(delete(Activity).where(Activity.subject_id.in_(ids)))
        db.execute(delete(Customer).where(Customer.id.in_(ids)))


def test_create_and_duplicate(client: TestClient, temp_name: str) -> None:
    body = {"name": temp_name, "industry": "测试", "level": "B"}
    r = client.post("/api/customers", json=body, headers=auth_header(Role.SALES))
    assert r.status_code == 200 and r.json()["data"]["owner"]["name"] == "张晨"
    dup = client.post("/api/customers", json=body, headers=auth_header(Role.SALES))
    assert dup.status_code == 409 and dup.json()["code"] == 40901


def test_create_validation(client: TestClient) -> None:
    r = client.post(
        "/api/customers", json={"name": "", "level": "Z"}, headers=auth_header(Role.SALES)
    )
    assert r.json()["code"] == 40001
