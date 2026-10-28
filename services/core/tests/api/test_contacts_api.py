"""联系人增删改与角色（B7 / U11）：只有客户负责人能改，按角色排序，动作写入客户动态。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect

from app.common.auth import Role
from app.common.db import get_engine, session_scope
from app.crm.models import Activity, Contact, Customer
from seed.data import C_MINGLI
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def require_seeded_db(db_available: bool) -> None:
    if not db_available:
        pytest.skip("DATABASE_URL 连不上，跳过需要数据库的用例")
    if not inspect(get_engine()).has_table("contacts"):
        pytest.skip("数据库未迁移")
    with session_scope() as db:
        if db.get(Customer, C_MINGLI) is None:
            pytest.skip("缺少演示数据（先执行 python -m seed）")


@pytest.fixture
def customer_id(client: TestClient) -> Iterator[str]:
    body = {"name": f"联系人测试-{uuid.uuid4().hex[:6]}", "level": "B"}
    r = client.post("/api/customers", json=body, headers=auth_header(Role.SALES))
    cid = r.json()["data"]["id"]
    yield cid
    with session_scope() as db:
        db.execute(delete(Contact).where(Contact.customer_id == uuid.UUID(cid)))
        db.execute(delete(Activity).where(Activity.subject_id == uuid.UUID(cid)))
        db.execute(delete(Customer).where(Customer.id == uuid.UUID(cid)))


def _url(cid: str, contact_id: str = "") -> str:
    return f"/api/customers/{cid}/contacts" + (f"/{contact_id}" if contact_id else "")


def test_contact_crud_roles_and_order(client: TestClient, customer_id: str) -> None:
    h = auth_header(Role.SALES)
    a = client.post(_url(customer_id), json={"name": "小李", "title": "工程师"}, headers=h)
    assert a.status_code == 200 and a.json()["data"]["role"] is None
    b = client.post(
        _url(customer_id),
        json={"name": "赵总", "title": "CEO", "role": "decision_maker"},
        headers=h,
    ).json()["data"]
    assert b["is_decision_maker"] is True
    items = client.get(_url(customer_id), headers=h).json()["data"]["items"]
    assert [c["name"] for c in items] == ["赵总", "小李"]  # 决策人在前

    r = client.patch(_url(customer_id, b["id"]), json={"role": "influencer"}, headers=h)
    assert (
        r.json()["data"]["role"] == "influencer" and r.json()["data"]["is_decision_maker"] is False
    )
    assert client.delete(_url(customer_id, a.json()["data"]["id"]), headers=h).json()["code"] == 0
    assert len(client.get(_url(customer_id), headers=h).json()["data"]["items"]) == 1

    acts = client.get(f"/api/activities?subject_type=customer&subject_id={customer_id}", headers=h)
    got = {(x["action"], x["content"]) for x in acts.json()["data"]["items"]}
    assert ("contact_added", "赵总（CEO · 决策人）") in got and ("contact_removed", "小李") in got


def test_only_owner_can_edit_contacts(client: TestClient, customer_id: str) -> None:
    body = {"name": "某人", "role": "user"}
    manager = client.post(_url(customer_id), json=body, headers=auth_header(Role.MANAGER))
    assert manager.status_code == 403 and manager.json()["data"]["rule"] == "not_owner"
    admin = client.post(_url(customer_id), json=body, headers=auth_header(Role.ADMIN))
    assert admin.status_code == 403
    bad = client.post(
        _url(customer_id), json={"name": "x", "role": "boss"}, headers=auth_header(Role.SALES)
    )
    assert bad.json()["code"] == 40001


def test_contact_of_other_customer_is_404(client: TestClient, customer_id: str) -> None:
    """联系人 id 必须属于路径里的客户，防止借自己的客户改别人的联系人。"""
    with session_scope() as db:
        other = db.query(Contact).filter(Contact.customer_id == C_MINGLI).first()
        assert other is not None
        other_id = str(other.id)
    r = client.patch(
        _url(customer_id, other_id), json={"name": "改名"}, headers=auth_header(Role.SALES)
    )
    assert r.status_code == 404
