"""操作日志、电话脱敏 / 查看限次、导出授权。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.agent.tools import TOOLS, ToolContext, run_tool
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import AuditLog
from app.crm.services.audit_service import match_route
from app.crm.services.contact_service import mask_phone
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker


@pytest.fixture
def customer(client: TestClient, tracker: Tracker) -> Iterator[dict]:
    body = {"name": f"审计测试-{uuid.uuid4().hex[:6]}", "level": "B"}
    r = client.post("/api/customers", json=body, headers=SALES_H)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    tracker.customers.append(uuid.UUID(data["id"]))
    yield data
    with session_scope() as db:
        db.execute(delete(AuditLog).where(AuditLog.path.like(f"%{data['id']}%")))
        db.execute(delete(AuditLog).where(AuditLog.detail == data["name"]))


def _logs(**where: object) -> list[AuditLog]:
    with session_scope() as db:
        stmt = select(AuditLog)
        for k, v in where.items():
            stmt = stmt.where(getattr(AuditLog, k) == v)
        rows = list(db.scalars(stmt.order_by(AuditLog.created_at)))
        db.expunge_all()
        return rows


def test_match_route() -> None:
    assert match_route("PATCH", "/api/customers/abc") == ("customer.update", "修改客户", "abc")
    hit = match_route("DELETE", "/api/customers/c1/contacts/k9")
    assert hit == ("contact.delete", "删除联系人", "k9")
    assert match_route("POST", "/api/expenses/precheck") is None  # 试算不记
    assert match_route("GET", "/api/customers") is None


def test_write_requests_are_logged_including_failures(client: TestClient, customer: dict) -> None:
    cid = customer["id"]
    rows = _logs(action="customer.create", target_id=None, path="/api/customers")
    assert any(r.user_name == DEMO_USERS[Role.SALES].name and r.ok for r in rows)

    r = client.patch(f"/api/customers/{cid}", json={"industry": "法律"}, headers=SALES_H)
    assert r.json()["code"] == 0
    # 同组另一名销售改别人的客户：被拒，也要留痕
    r = client.patch(f"/api/customers/{cid}", json={"industry": "x"}, headers=SALES2_H)
    assert r.json()["code"] != 0
    logs = _logs(action="customer.update", target_id=cid)
    assert [log.ok for log in logs] == [True, False]
    assert logs[1].status == r.json()["code"] and logs[1].detail


def test_audit_list_permissions(client: TestClient, customer: dict) -> None:
    assert client.get("/api/audit-logs", headers=SALES_H).json()["code"] == 40301
    page = client.get(
        "/api/audit-logs", params={"q": customer["name"][:2]}, headers=ADMIN_H
    ).json()["data"]
    assert page["total"] >= 0
    mine = client.get(
        "/api/audit-logs", params={"action": "customer.create"}, headers=MANAGER_H
    ).json()["data"]
    assert mine["items"] and all(i["action"] == "customer.create" for i in mine["items"])
    cid = customer["id"]
    client.patch(f"/api/customers/{cid}", json={"industry": "法律"}, headers=SALES_H)
    hit = client.get("/api/audit-logs", params={"action": "customer.update"}, headers=MANAGER_H)
    named = [i for i in hit.json()["data"]["items"] if i["target_id"] == cid]
    assert named and named[0]["target_name"] == customer["name"]


def test_phone_masked_and_reveal_logged(client: TestClient, customer: dict) -> None:
    cid = customer["id"]
    r = client.post(
        f"/api/customers/{cid}/contacts",
        json={"name": "测试联系人", "phone": "13900002222"},
        headers=SALES_H,
    )
    item = r.json()["data"]
    assert item["phone"] == "139****2222" and item["has_phone"] is True
    listed = client.get(f"/api/customers/{cid}/contacts", headers=MANAGER_H).json()["data"]
    assert listed["items"][0]["phone"] == "139****2222"

    # 编辑时原样提交脱敏号码：电话不变
    url = f"/api/customers/{cid}/contacts/{item['id']}"
    client.patch(url, json={"title": "主任", "phone": "139****2222"}, headers=SALES_H)
    r = client.post(f"{url}/phone", headers=MANAGER_H)
    assert r.json()["data"]["phone"] == "13900002222"
    logs = _logs(action="contact.phone_view", target_id=item["id"])
    assert len(logs) == 1 and logs[0].user_name == DEMO_USERS[Role.MANAGER].name
    with session_scope() as db:
        db.execute(delete(AuditLog).where(AuditLog.target_id == item["id"]))


def test_phone_reveal_daily_limit(client: TestClient, customer: dict) -> None:
    cid = customer["id"]
    item = client.post(
        f"/api/customers/{cid}/contacts",
        json={"name": "限次测试", "phone": "13900003333"},
        headers=SALES_H,
    ).json()["data"]
    url = f"/api/customers/{cid}/contacts/{item['id']}/phone"
    set_limit = {"values": {"privacy.phone_reveal_daily_limit": 0}}
    assert client.put("/api/settings/rules", json=set_limit, headers=ADMIN_H).json()["code"] == 0
    try:
        r = client.post(url, headers=SALES_H)
        assert r.json()["code"] == 42901
        assert [log.ok for log in _logs(target_id=item["id"])] == [False]
    finally:
        reset = {"values": {"privacy.phone_reveal_daily_limit": None}}
        client.put("/api/settings/rules", json=reset, headers=ADMIN_H)
        with session_scope() as db:
            db.execute(delete(AuditLog).where(AuditLog.target_id == item["id"]))
            db.execute(delete(AuditLog).where(AuditLog.action == "settings.rules"))


def test_export_requires_role_and_row_limit(client: TestClient) -> None:
    r = client.post("/api/exports", json={"entity": "customers", "rows": 10}, headers=SALES_H)
    assert r.json()["code"] == 40301
    assert "不能导出客户" in r.json()["message"]
    r = client.post("/api/exports", json={"entity": "quotes", "rows": 10}, headers=SALES_H)
    assert r.json()["data"]["allowed"] is True
    r = client.post("/api/exports", json={"entity": "customers", "rows": 5000}, headers=MANAGER_H)
    assert r.json()["code"] == 40301
    with session_scope() as db:
        db.execute(delete(AuditLog).where(AuditLog.action.like("export.%")))


def test_mask_phone() -> None:
    assert mask_phone("13900002222") == "139****2222"
    assert mask_phone("1234") == "**34"
    assert mask_phone(None) is None


def test_agent_write_tool_is_logged() -> None:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id="t-audit")
    # 不存在的客户：工具失败，也记一条 source=agent 的失败日志
    bogus = str(uuid.uuid4())
    result = run_tool(
        TOOLS["add_followup"], ctx, {"customer_id": bogus, "content": "x"}, lambda *_: None
    )
    assert not result.ok
    with session_scope() as db:
        rows = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.source == "agent", AuditLog.extra["thread_id"].astext == "t-audit"
                )
            )
        )
        assert rows and rows[-1].action == "followup.create" and not rows[-1].ok
        db.execute(delete(AuditLog).where(AuditLog.extra["thread_id"].astext == "t-audit"))


def test_audit_list_can_hide_logins(client: TestClient) -> None:
    marker = f"login-{uuid.uuid4().hex[:6]}"
    with session_scope() as db:
        db.add(AuditLog(action="auth.login", label="登录", detail=marker, ok=True, status=200))
    try:
        params = {"q": marker}
        shown = client.get("/api/audit-logs", params=params, headers=ADMIN_H).json()["data"]
        assert shown["total"] == 1
        hidden = client.get(
            "/api/audit-logs", params={**params, "exclude": "auth."}, headers=ADMIN_H
        ).json()["data"]
        assert hidden["total"] == 0
    finally:
        with session_scope() as db:
            db.execute(delete(AuditLog).where(AuditLog.detail == marker))
