"""演示组织：两个团队互相隔离、分享前统一重置演示账号密码（需要数据库）。"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.config import get_settings
from app.common.db import session_scope
from app.common.passwords import hash_password, verify_password
from app.crm.models import Contact, Customer, Team, User
from app.crm.services.demo import EAST_MANAGER, EAST_SALES
from seed import data
from seed.__main__ import seed_org


def _login(client: TestClient, username: str) -> dict:
    body = {"username": username, "password": get_settings().demo_password}
    return client.post("/api/auth/login", json=body).json()


def test_east_team_has_manager_and_own_customers(client: TestClient) -> None:
    with session_scope() as db:
        team = db.get(Team, data.TEAM_EAST["id"])
        assert team is not None and team.manager_id == EAST_MANAGER.id
        owners = set(db.scalars(select(Customer.owner_id).where(Customer.team_id == team.id)))
        assert owners <= {u.id for u in EAST_SALES} and owners
        # 回归：联系人原来一律记在张晨名下，华东的客户报客户招待时选不到客户方参与人
        contact_owners = set(
            db.scalars(
                select(Contact.owner_id)
                .join(Customer, Customer.id == Contact.customer_id)
                .where(Customer.team_id == team.id)
            )
        )
        assert contact_owners and contact_owners <= {u.id for u in EAST_SALES}

    token = _login(client, "chenjing")["data"]["token"]
    names = {
        c["name"]
        for c in client.get(
            "/api/customers",
            params={"page_size": 100},
            headers={"Authorization": f"Bearer {token}"},
        ).json()["data"]["items"]
    }
    assert "杭州青禾电商" in names and "深圳明理律师事务所" not in names


def test_reset_passwords_restores_demo_password() -> None:
    with session_scope() as db:
        user = db.get(User, EAST_SALES[1].id)
        assert user is not None
        user.password_hash, user.must_change_password = hash_password("Changed#2026x"), True
    with session_scope() as db:
        seed_org(db)  # 默认不覆盖改过的密码
        user = db.get(User, EAST_SALES[1].id)
        assert user is not None and not verify_password(
            get_settings().demo_password, user.password_hash
        )
        seed_org(db, reset_passwords=True)
        assert verify_password(get_settings().demo_password, user.password_hash)
        assert not user.must_change_password


def test_east_sales_dashboard_has_activities(client: TestClient) -> None:
    """回归：华东组销售登录后工作台「我的动态」是空的，演示数据只给张晨写了动态。"""
    token = _login(client, "liuyang")["data"]["token"]
    body = client.get(
        "/api/activities", params={"view": "mine"}, headers={"Authorization": f"Bearer {token}"}
    ).json()
    contents = [a["content"] for a in body["data"]["items"]]
    assert any("会员积分" in c for c in contents)
    assert not any("明理" in (c or "") for c in contents)


def test_demo_overdue_contract_periods_in_order() -> None:
    """回归：演示逾期时只把第 2 期改到 5 天前，第 1 期预付款的到期日反而更晚。"""
    from app.crm.models import PaymentPlan
    from app.crm.services.demo import demo_id

    with session_scope() as db:
        plans = db.scalars(
            select(PaymentPlan)
            .where(PaymentPlan.contract_id == demo_id("contract:yuehai"))
            .order_by(PaymentPlan.seq)
        ).all()
    dues = [p.due_date for p in plans]
    assert len(dues) >= 3 and dues == sorted(dues)
