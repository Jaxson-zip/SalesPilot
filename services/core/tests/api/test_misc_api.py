"""行业包配置、客户跟进 / 联系人、Agent 工具对接新 service（接口契约 §7、§8、§9）。"""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.agent.tools import TOOLS, ToolContext, run_tool
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import ProductLine
from app.crm.services.demo import DEMO_USERS, demo_id
from seed.data import C_MINGLI, C_PC3H, PL_IT
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.api.test_opportunities_api import new_opp


def test_product_lines_readable_by_all_roles(client: TestClient) -> None:
    """销售建商机时要选产品线，所以列表所有角色可读；修改仍仅限管理员。"""
    for headers in (SALES_H, MANAGER_H):
        r = client.get("/api/product-lines", headers=headers).json()
        assert r["code"] == 0 and r["data"]["items"]
    items = client.get("/api/product-lines", headers=ADMIN_H).json()["data"]["items"]
    llm = next(x for x in items if x["pack"] == "llm_deploy")
    assert set(llm) == {"id", "name", "pack", "enabled", "open_opportunities"}
    assert llm["open_opportunities"] >= 3


def test_disabled_product_line_hidden_from_sales(client: TestClient) -> None:
    try:
        client.put(f"/api/product-lines/{PL_IT}", json={"enabled": False}, headers=ADMIN_H)
        sales = client.get("/api/product-lines", headers=SALES_H).json()["data"]["items"]
        admin = client.get("/api/product-lines", headers=ADMIN_H).json()["data"]["items"]
        assert str(PL_IT) not in {x["id"] for x in sales}
        assert str(PL_IT) in {x["id"] for x in admin}
    finally:
        with session_scope() as db:
            line = db.get(ProductLine, PL_IT)
            assert line is not None
            line.enabled = True


def test_product_line_update(client: TestClient) -> None:
    url = f"/api/product-lines/{PL_IT}"
    try:
        r = client.put(url, json={"enabled": False}, headers=ADMIN_H).json()["data"]
        assert r["enabled"] is False and r["pack"] == "it_office"
        bad = client.put(url, json={"pack": "not_installed"}, headers=ADMIN_H).json()
        assert bad["code"] == 40001
        assert client.put(url, json={"enabled": True}, headers=SALES_H).json()["code"] == 40301
        missing = client.put(f"/api/product-lines/{uuid.uuid4()}", json={}, headers=ADMIN_H)
        assert missing.json()["code"] == 40401
    finally:
        with session_scope() as db:
            line = db.get(ProductLine, PL_IT)
            assert line is not None
            line.enabled, line.pack = True, "it_office"


def test_followups(client: TestClient, tracker: Tracker) -> None:
    url = f"/api/customers/{C_MINGLI}/followups"
    body = {
        "type": "email",
        "content": "测试-发送方案邮件",
        "occurred_at": "2026-10-20T10:00:00+08:00",
    }
    r = client.post(url, json=body, headers=SALES_H).json()["data"]
    tracker.followups.append(uuid.UUID(r["id"]))
    assert r["type"] == "email" and r["source"] == "manual"
    items = client.get(f"{url}?limit=50", headers=SALES_H).json()["data"]["items"]
    assert r["id"] in {f["id"] for f in items}
    assert (
        client.post(url, json={"type": "ai", "content": "x"}, headers=SALES_H).json()["code"]
        == 40001
    )
    other = f"/api/customers/{C_PC3H}/followups"
    assert client.get(other, headers=SALES_H).json()["code"] == 40401
    assert client.post(other, json=body, headers=SALES_H).json()["code"] == 40401


def test_followup_opportunity_must_match_customer(client: TestClient) -> None:
    body = {"type": "phone", "content": "测试", "opportunity_id": str(demo_id("opp:hnzz"))}
    r = client.post(f"/api/customers/{C_MINGLI}/followups", json=body, headers=SALES_H)
    assert r.json()["code"] == 40001


def test_contacts(client: TestClient) -> None:
    items = client.get(f"/api/customers/{C_MINGLI}/contacts", headers=SALES_H).json()["data"][
        "items"
    ]
    assert items[0]["name"] == "王律师" and items[0]["is_decision_maker"]
    r = client.get(f"/api/customers/{C_PC3H}/contacts", headers=SALES_H)
    assert r.status_code == 404 and r.json()["code"] == 40401


def _ctx(role: Role) -> ToolContext:
    return ToolContext(user=DEMO_USERS[role], session=session_scope, thread_id="t-api")


def _call(role: Role, name: str, args: dict) -> object:
    return run_tool(TOOLS[name], _ctx(role), args, lambda *_: None)


def test_tool_update_stage_reuses_rules(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    args = {"opportunity_id": opp["id"], "stage": "lost", "idempotency_key": "k1"}
    missing = _call(Role.SALES, "update_opportunity_stage", args)
    assert not missing.ok and missing.error["code"] == 40001  # type: ignore[attr-defined]
    done = _call(Role.SALES, "update_opportunity_stage", {**args, "lost_reason": "预算取消"})
    assert done.ok and "输单" in done.summary  # type: ignore[attr-defined]
    final = _call(Role.SALES, "update_opportunity_stage", {**args, "stage": "won"})
    assert final.error["code"] == 42201  # type: ignore[attr-defined]


def test_tool_submit_expense_and_decide(tracker: Tracker) -> None:
    args = {"type": "entertainment", "amount": 86_000, "headcount": 4,
            "occurred_on": date(2026, 10, 24).isoformat(), "customer_id": str(C_MINGLI),
            "reason": "测试-Agent 报销", "idempotency_key": uuid.uuid4().hex}  # fmt: skip
    res = _call(Role.SALES, "submit_expense", args)
    assert res.ok and res.data["status"] == "draft"  # type: ignore[attr-defined]
    tracker.expenses.append(uuid.UUID(res.data["id"]))  # type: ignore[attr-defined]
    assert "上传发票" in res.summary  # type: ignore[attr-defined]
    dup = _call(Role.SALES, "submit_expense", args)
    assert dup.error["code"] == 40901  # type: ignore[attr-defined]
    approval = {"approval_id": str(uuid.uuid4()), "decision": "approve"}
    assert _call(Role.SALES, "decide_approval", approval).error["code"] == 40301  # type: ignore[attr-defined]
    assert _call(Role.MANAGER, "decide_approval", approval).error["code"] == 40401  # type: ignore[attr-defined]


def test_tool_pipeline_summary() -> None:
    res = _call(Role.SALES, "pipeline_summary", {})
    assert res.ok and "weighted_amount" in res.data  # type: ignore[attr-defined]
