"""账号体系：账号密码登录、改密码、管理员管理成员和团队、停用后立即失效。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.common.auth import forget_user
from app.common.config import get_settings
from app.common.db import session_scope
from app.crm.models import Customer, Notification, Team, User
from app.crm.services import auth_service
from app.crm.services.demo import EXTRA_SALES, TEAM_SOUTH_ID
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H

ADMIN_URL = "/api/admin/users"


def login(client: TestClient, username: str, password: str) -> dict:
    return client.post("/api/auth/login", json={"username": username, "password": password}).json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cleanup() -> Iterator[dict[str, list]]:
    """记下测试里新建的成员 / 团队 / 客户，结束后删除。"""
    made: dict[str, list] = {"users": [], "teams": [], "customers": []}
    auth_service._failures.clear()
    yield made
    auth_service._failures.clear()
    with session_scope() as db:
        db.execute(delete(Customer).where(Customer.id.in_(made["customers"])))
        db.execute(
            delete(Notification).where(
                Notification.type == "customer_handover", Notification.title.contains("测试成员")
            )
        )
        db.execute(
            delete(Notification).where(
                Notification.type == "account_deactivated",
                Notification.link.in_([f"/customers?handover={u}" for u in made["users"]]),
            )
        )
        db.execute(delete(User).where(User.id.in_(made["users"])))
        db.execute(delete(Team).where(Team.id.in_(made["teams"])))
    forget_user()


def new_member(client: TestClient, made: dict, **extra: object) -> dict:
    username = f"t{uuid.uuid4().hex[:8]}"
    body = {
        "username": username,
        "name": "测试成员",
        "role": "sales",
        "team_id": str(TEAM_SOUTH_ID),
    }
    r = client.post(ADMIN_URL, json={**body, **extra}, headers=ADMIN_H).json()
    assert r["code"] == 0, r
    made["users"].append(uuid.UUID(r["data"]["account"]["id"]))
    return r["data"]


def test_demo_account_password_login(client: TestClient, cleanup: dict) -> None:
    r = login(client, "ZhangChen", "demo2026")  # 登录名不区分大小写
    assert r["code"] == 0 and r["data"]["user"]["name"] == "张晨"
    assert r["data"]["user"]["team_name"] and r["data"]["user"]["username"] == "zhangchen"
    me = client.get("/api/me", headers=bearer(r["data"]["token"])).json()["data"]
    assert me["role"] == "sales" and me["must_change_password"] is False
    wrong = client.post("/api/auth/login", json={"username": "zhangchen", "password": "nope1234"})
    assert wrong.status_code == 401 and wrong.json()["message"] == "账号或密码不正确"
    nobody = login(client, "nobody", "demo2026")
    assert nobody["message"] == "账号或密码不正确"  # 不暴露账号是否存在


def test_wrong_password_locks_after_ten(client: TestClient, cleanup: dict) -> None:
    for _ in range(auth_service.MAX_FAILURES):
        assert login(client, "wanglei", "bad-pass1")["code"] == 40101
    locked = client.post("/api/auth/login", json={"username": "wanglei", "password": "demo2026"})
    assert locked.status_code == 429 and locked.json()["data"]["rule"] == "login_locked"


def test_admin_creates_member_who_must_change_password(client: TestClient, cleanup: dict) -> None:
    created = new_member(client, cleanup)
    account, temp = created["account"], created["temp_password"]
    assert account["must_change_password"] is True and account["team_name"]
    first = login(client, account["username"], temp)["data"]
    assert first["user"]["must_change_password"] is True
    token = first["token"]
    weak = client.post(
        "/api/auth/password",
        json={"old_password": temp, "new_password": "short"},
        headers=bearer(token),
    ).json()
    assert weak["code"] == 40001 and weak["data"]["rule"] == "weak_password"
    changed = client.post(
        "/api/auth/password",
        json={"old_password": temp, "new_password": "NewPass2026"},
        headers=bearer(token),
    ).json()
    assert changed["code"] == 0 and changed["data"]["user"]["must_change_password"] is False
    # 改密码后旧 token 作废，新 token 可用
    assert client.get("/api/me", headers=bearer(token)).status_code == 401
    assert client.get("/api/me", headers=bearer(changed["data"]["token"])).json()["code"] == 0
    assert login(client, account["username"], "NewPass2026")["code"] == 0


def test_create_rules(client: TestClient, cleanup: dict) -> None:
    created = new_member(client, cleanup)
    dup = {"username": created["account"]["username"].upper(), "name": "重名", "role": "sales",
           "team_id": str(TEAM_SOUTH_ID)}  # fmt: skip
    assert client.post(ADMIN_URL, json=dup, headers=ADMIN_H).json()["code"] == 40901
    no_team = {"username": f"t{uuid.uuid4().hex[:8]}", "name": "无团队", "role": "manager"}
    r = client.post(ADMIN_URL, json=no_team, headers=ADMIN_H).json()
    assert r["code"] == 40001 and r["data"]["rule"] == "team_required"
    bad_name = {**no_team, "username": "中文名", "team_id": str(TEAM_SOUTH_ID)}
    assert client.post(ADMIN_URL, json=bad_name, headers=ADMIN_H).json()["code"] == 40001
    for headers in (SALES_H, MANAGER_H):
        assert client.get(ADMIN_URL, headers=headers).json()["code"] == 40301
    # 管理员不属于团队：传了也忽略
    admin = new_member(client, cleanup, role="admin")["account"]
    assert admin["team_id"] is None


def test_deactivate_kicks_out_and_notifies_manager(client: TestClient, cleanup: dict) -> None:
    created = new_member(client, cleanup)
    uid, username = created["account"]["id"], created["account"]["username"]
    token = login(client, username, created["temp_password"])["data"]["token"]
    with session_scope() as db:
        customer = Customer(name=f"停用测试客户-{uid[:6]}", owner_id=uid, team_id=TEAM_SOUTH_ID)
        db.add(customer)
        db.flush()
        cleanup["customers"].append(customer.id)
    r = client.patch(f"{ADMIN_URL}/{uid}", json={"active": False}, headers=ADMIN_H).json()
    assert r["code"] == 0 and r["data"]["active"] is False and r["data"]["customers"] == 1
    assert client.get("/api/me", headers=bearer(token)).status_code == 401
    blocked = client.post(
        "/api/auth/login", json={"username": username, "password": created["temp_password"]}
    )
    assert blocked.json()["code"] == 40301 and blocked.json()["data"]["rule"] == "account_inactive"
    notes = client.get("/api/notifications?limit=100", headers=MANAGER_H).json()["data"]["items"]
    assert any(
        n["type"] == "account_deactivated" and n["link"] == f"/customers?handover={uid}"
        for n in notes
    )
    # 同事列表默认不含停用成员；交接时可以带上
    users = client.get("/api/users", headers=MANAGER_H).json()["data"]["items"]
    assert uid not in {u["id"] for u in users}
    with_inactive = client.get("/api/users?include_inactive=true", headers=MANAGER_H).json()
    assert any(u["id"] == uid and u["active"] is False for u in with_inactive["data"]["items"])
    # 不能把客户转给停用的成员
    to_inactive = {"customer_ids": [str(cleanup["customers"][0])], "to_user_id": uid}
    r = client.post("/api/customers/transfer", json=to_inactive, headers=MANAGER_H).json()
    assert r["code"] == 42201 and r["data"]["rule"] == "user_inactive"
    # 交接给王磊
    body = {"from_user_id": uid, "to_user_id": str(EXTRA_SALES.id)}
    assert client.post("/api/customers/handover", json=body, headers=MANAGER_H).json()["code"] == 0


def test_role_change_takes_effect_and_reset_password(client: TestClient, cleanup: dict) -> None:
    created = new_member(client, cleanup)
    uid = created["account"]["id"]
    token = login(client, created["account"]["username"], created["temp_password"])["data"]["token"]
    r = client.patch(f"{ADMIN_URL}/{uid}", json={"role": "manager"}, headers=ADMIN_H).json()
    assert r["data"]["role"] == "manager"
    # 角色以库里为准：同一个 token 马上变成主管
    assert client.get("/api/me", headers=bearer(token)).json()["data"]["role"] == "manager"
    reset = client.post(f"{ADMIN_URL}/{uid}/reset-password", headers=ADMIN_H).json()["data"]
    assert reset["account"]["must_change_password"] is True
    assert client.get("/api/me", headers=bearer(token)).status_code == 401
    assert login(client, created["account"]["username"], reset["temp_password"])["code"] == 0


def test_cannot_lock_out_admins(client: TestClient, cleanup: dict) -> None:
    with session_scope() as db:
        admin_id = db.scalar(select(User.id).where(User.username == "zhoumin"))
    me = client.patch(f"{ADMIN_URL}/{admin_id}", json={"active": False}, headers=ADMIN_H).json()
    assert me["code"] == 42201 and me["data"]["rule"] == "account_self"
    demote = client.patch(f"{ADMIN_URL}/{admin_id}", json={"role": "sales"}, headers=ADMIN_H)
    assert demote.json()["data"]["rule"] == "account_self"


def test_teams(client: TestClient, cleanup: dict) -> None:
    name = f"测试团队-{uuid.uuid4().hex[:6]}"
    r = client.post("/api/admin/teams", json={"name": name}, headers=ADMIN_H).json()
    assert r["code"] == 0 and r["data"]["members"] == 0
    cleanup["teams"].append(uuid.UUID(r["data"]["id"]))
    dup = client.post("/api/admin/teams", json={"name": name}, headers=ADMIN_H).json()
    assert dup["code"] == 40901
    renamed = client.patch(
        f"/api/admin/teams/{r['data']['id']}", json={"name": name + "改"}, headers=ADMIN_H
    ).json()
    assert renamed["data"]["name"] == name + "改"
    member = new_member(client, cleanup, team_id=r["data"]["id"])
    assert member["account"]["team_name"] == name + "改"
    teams = client.get("/api/admin/teams", headers=ADMIN_H).json()["data"]
    south = next(t for t in teams if t["id"] == str(TEAM_SOUTH_ID))
    assert "李薇" in south["managers"]


def test_team_default_pack(client: TestClient, cleanup: dict) -> None:
    """管理员给团队指定默认产品线：成员不从商机进入 AI 时用它对应的行业包。"""
    lines = client.get("/api/product-lines", headers=ADMIN_H).json()["data"]["items"]
    line = next(x for x in lines if x["enabled"] and x["pack"] != get_settings().default_pack)
    name = f"测试团队-{uuid.uuid4().hex[:6]}"
    body = {"name": name, "default_product_line_id": line["id"]}
    team = client.post("/api/admin/teams", json=body, headers=ADMIN_H).json()["data"]
    cleanup["teams"].append(uuid.UUID(team["id"]))
    assert team["default_product_line"] == line["name"] and team["pack"] == line["pack"]
    member = new_member(client, cleanup, team_id=team["id"])
    token = login(client, member["account"]["username"], member["temp_password"])["data"]["token"]
    pack = client.get("/api/agent/pack", headers=bearer(token)).json()["data"]
    assert pack == {"pack": line["pack"], "product_line": line["name"]}
    # 只改名：产品线不变；传 null：回到系统默认行业包
    url = f"/api/admin/teams/{team['id']}"
    renamed = client.patch(url, json={"name": name + "改"}, headers=ADMIN_H).json()["data"]
    assert renamed["pack"] == line["pack"]
    body = {"name": name, "default_product_line_id": None}
    reset = client.patch(url, json=body, headers=ADMIN_H).json()["data"]
    assert reset["pack"] is None
    pack = client.get("/api/agent/pack", headers=bearer(token)).json()["data"]
    assert pack == {"pack": get_settings().default_pack, "product_line": None}
    bad = {"name": name, "default_product_line_id": str(uuid.uuid4())}
    assert client.patch(url, json=bad, headers=ADMIN_H).status_code == 404
