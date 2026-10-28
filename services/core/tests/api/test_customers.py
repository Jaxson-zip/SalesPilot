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
        ids = [c.id for c in db.query(Customer).filter(Customer.name.startswith(name))]
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


def test_similar_customers_across_company_hides_invisible_ids(client: TestClient) -> None:
    """查重是全公司范围：销售看不到的客户也会提示，但只给名称和负责人。"""
    r = client.get("/api/customers/similar?name=明理律师事务所", headers=auth_header(Role.SALES))
    first = r.json()["data"][0]
    assert first["name"] == "深圳明理律师事务所" and first["visible"] and first["id"]
    r = client.get("/api/customers/similar?name=鹏城第三人民医院", headers=auth_header(Role.SALES))
    hidden = r.json()["data"][0]
    assert hidden["name"] == "鹏城第三人民医院" and hidden["exact"]
    assert hidden["visible"] is False and hidden["id"] is None and hidden["owner_name"]


def test_create_rejects_same_core_name(client: TestClient, temp_name: str) -> None:
    """「X 有限公司」和「X（深圳）」算同一个客户。"""
    body = {"name": f"{temp_name}有限公司", "level": "B"}
    assert (
        client.post("/api/customers", json=body, headers=auth_header(Role.SALES)).status_code == 200
    )
    dup = {"name": f"{temp_name}（深圳）", "level": "B"}
    r = client.post("/api/customers", json=dup, headers=auth_header(Role.SALES))
    assert r.status_code == 409 and temp_name in r.json()["message"]


def test_update_customer_inline(client: TestClient, temp_name: str) -> None:
    """U10：负责人改字段，写入动态；改成别的客户的名字被拒；主管不能改。"""
    h = auth_header(Role.SALES)
    cid = client.post("/api/customers", json={"name": temp_name, "level": "C"}, headers=h).json()[
        "data"
    ]["id"]
    r = client.patch(
        f"/api/customers/{cid}", json={"level": "A", "annual_budget": 50_000_000}, headers=h
    )
    data = r.json()["data"]
    assert data["level"] == "A" and data["annual_budget"] == 50_000_000
    cleared = client.patch(f"/api/customers/{cid}", json={"address": None}, headers=h)
    assert cleared.json()["data"]["address"] is None
    dup = client.patch(f"/api/customers/{cid}", json={"name": "深圳明理律师事务所"}, headers=h)
    assert dup.status_code == 409
    renamed = client.patch(f"/api/customers/{cid}", json={"name": f"{temp_name}（改）"}, headers=h)
    assert renamed.json()["code"] == 0  # 与自己核心名相同不算重复
    manager = client.patch(
        f"/api/customers/{cid}", json={"level": "B"}, headers=auth_header(Role.MANAGER)
    )
    assert manager.status_code in (403, 404)
    acts = client.get(f"/api/activities?subject_type=customer&subject_id={cid}", headers=h).json()
    assert any((a["content"] or "") == "等级、年度预算" for a in acts["data"]["items"])
