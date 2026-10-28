"""客户公海（B5）：退回 → 本团队可见、只读 → 同事领取 / 主管分配；有进行中商机不能退回。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.common.db import session_scope
from app.crm.models import Activity, Contact, Customer, Opportunity
from app.crm.services.demo import EXTRA_SALES
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H


@pytest.fixture
def customer_id(client: TestClient) -> Iterator[str]:
    body = {"name": f"公海测试-{uuid.uuid4().hex[:6]}", "level": "C"}
    cid = client.post("/api/customers", json=body, headers=SALES_H).json()["data"]["id"]
    client.post(f"/api/customers/{cid}/contacts", json={"name": "钱经理"}, headers=SALES_H)
    yield cid
    key = uuid.UUID(cid)
    with session_scope() as db:
        opp_ids = list(
            db.scalars(
                Opportunity.__table__.select()
                .with_only_columns(Opportunity.id)
                .where(Opportunity.customer_id == key)
            )
        )
        db.execute(delete(Activity).where(Activity.subject_id.in_([key, *opp_ids])))
        db.execute(delete(Opportunity).where(Opportunity.customer_id == key))
        db.execute(delete(Contact).where(Contact.customer_id == key))
        db.execute(delete(Customer).where(Customer.id == key))


def _pool_ids(client: TestClient, headers: dict[str, str]) -> set[str]:
    r = client.get("/api/customers/pool?page_size=100", headers=headers)
    assert r.status_code == 200
    return {c["id"] for c in r.json()["data"]["items"]}


def test_release_then_teammate_claims(client: TestClient, customer_id: str) -> None:
    url = f"/api/customers/{customer_id}"
    # 退回要写原因；同事不能替负责人退回
    assert client.post(f"{url}/release", json={"reason": ""}, headers=SALES_H).status_code == 400
    assert client.post(f"{url}/release", json={"reason": "x"}, headers=SALES2_H).status_code == 404

    r = client.post(f"{url}/release", json={"reason": "预算冻结，半年内不采购"}, headers=SALES_H)
    assert r.status_code == 200 and r.json()["data"]["owner"] is None
    assert (
        client.post(f"{url}/release", json={"reason": "再退"}, headers=SALES_H).status_code == 409
    )

    # 本团队都能在公海里看到；原负责人的「我的客户」里不再有它
    assert customer_id in _pool_ids(client, SALES2_H)
    assert customer_id in _pool_ids(client, MANAGER_H)
    mine = client.get("/api/customers?page_size=100", headers=SALES_H).json()["data"]["items"]
    assert customer_id not in {c["id"] for c in mine}
    # 公海客户只读：详情能看，不能改
    assert client.get(url, headers=SALES2_H).status_code == 200
    assert client.patch(url, json={"level": "A"}, headers=SALES2_H).status_code == 403

    # 主管 / 管理员不能领取；同事领取后联系人一起过去，再领 409
    assert client.post(f"{url}/claim", headers=MANAGER_H).status_code == 403
    assert client.post(f"{url}/claim", headers=ADMIN_H).status_code == 403
    claimed = client.post(f"{url}/claim", headers=SALES2_H)
    assert claimed.json()["data"]["owner"]["id"] == str(EXTRA_SALES.id)
    assert client.post(f"{url}/claim", headers=SALES_H).status_code in (404, 409)
    with session_scope() as db:
        contact = db.query(Contact).filter(Contact.customer_id == uuid.UUID(customer_id)).one()
        assert contact.owner_id == EXTRA_SALES.id
    acts = client.get(
        f"/api/activities?subject_type=customer&subject_id={customer_id}", headers=SALES2_H
    ).json()["data"]["items"]
    actions = {a["action"] for a in acts}
    assert {"pool_release", "pool_claim"} <= actions


def test_release_blocked_by_open_opportunity(client: TestClient, customer_id: str) -> None:
    body = {"customer_id": customer_id, "name": "公海拦截商机", "amount": 100_00}
    assert client.post("/api/opportunities", json=body, headers=SALES_H).status_code == 200
    r = client.post(
        f"/api/customers/{customer_id}/release", json={"reason": "不跟了"}, headers=SALES_H
    )
    assert r.status_code == 422
    assert r.json()["data"]["rule"] == "has_open_opportunities"


def test_manager_releases_and_assigns(client: TestClient, customer_id: str) -> None:
    url = f"/api/customers/{customer_id}"
    r = client.post(f"{url}/release", json={"reason": "负责人离职"}, headers=MANAGER_H)
    assert r.status_code == 200
    body = {"customer_ids": [customer_id], "to_user_id": str(EXTRA_SALES.id)}
    moved = client.post("/api/customers/transfer", json=body, headers=MANAGER_H)
    assert moved.json()["data"]["transferred"] == 1
    assert customer_id not in _pool_ids(client, MANAGER_H)
