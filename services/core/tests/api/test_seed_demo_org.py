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
        user.token_version -= 1  # 其他用例用的是预先签发的 token，把这次重置带来的版本号加一撤回


def test_reset_passwords_revokes_old_tokens(client: TestClient) -> None:
    """回归：--reset-passwords 改了密码，之前登录拿到的 token 仍能以原身份访问。"""
    uid = EAST_SALES[1].id
    with session_scope() as db:
        user = db.get(User, uid)
        assert user is not None
        version = user.token_version
        user.password_hash = hash_password("Changed#2026x")
    body = {"username": "zhaoting", "password": "Changed#2026x"}
    token = client.post("/api/auth/login", json=body).json()["data"]["token"]
    me = {"Authorization": f"Bearer {token}"}
    try:
        assert client.get("/api/me", headers=me).json()["code"] == 0
        with session_scope() as db:
            seed_org(db, reset_passwords=True)
        assert client.get("/api/me", headers=me).json()["code"] == 40101
        assert _login(client, "zhaoting")["code"] == 0
        with session_scope() as db:  # 密码没变时再跑一次，不应把人踢下线
            seed_org(db, reset_passwords=True)
            user = db.get(User, uid)
            assert user is not None and user.token_version == version + 1
    finally:  # 其他用例用的是预先签发的 token，恢复版本号
        with session_scope() as db:
            user = db.get(User, uid)
            assert user is not None
            user.token_version = version


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


def test_demo_login_by_username_enters_east_accounts(client: TestClient) -> None:
    """演示切换原来只能按角色进张晨 / 李薇 / 周敏，华东组要输密码。"""
    body = client.post("/api/auth/mock-login", json={"role": "sales", "username": "liuyang"})
    user = body.json()["data"]["user"]
    assert user["name"] == "刘洋" and user["role"] == "sales"
    manager = client.post("/api/auth/mock-login", json={"role": "manager", "username": "chenjing"})
    assert manager.json()["data"]["user"]["name"] == "陈静"


def test_demo_login_by_username_rejects_mismatch(client: TestClient) -> None:
    # 角色对不上、不是演示账户：都不能一键登录
    wrong_role = client.post("/api/auth/mock-login", json={"role": "admin", "username": "liuyang"})
    assert wrong_role.json()["code"] == 40001
    not_demo = client.post("/api/auth/mock-login", json={"role": "sales", "username": "someone"})
    assert not_demo.json()["code"] == 40001
