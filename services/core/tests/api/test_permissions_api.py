"""角色与操作权限矩阵（接口契约 §0）：看得到 ≠ 改得了。

- 管理员写业务数据 → 40301 role_forbidden
- 主管改销售负责的记录 → 40301 not_owner；主管对自己负责的记录正常
- 审批、回款仅主管（本团队）
"""

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.agent.tools import TOOLS, ToolContext, ToolResult, run_tool
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Activity, Customer, Followup
from app.crm.services.demo import DEMO_USERS
from seed.data import C_MINGLI
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker, make_tier
from tests.api.test_expenses_approvals_api import PDF, PNG, new_expense, with_receipts
from tests.api.test_opportunities_api import OPP_MINGLI, new_opp
from tests.api.test_quotes_contracts_api import GOOD, LOW, _accepted_contract, act, create_quote

MANAGER = DEMO_USERS[Role.MANAGER]


def assert_forbidden(resp: Any, rule: str) -> None:
    body = resp.json() if hasattr(resp, "json") else resp
    assert body["code"] == 40301 and body["data"]["rule"] == rule, body


def _call(role: Role, name: str, args: dict[str, Any]) -> ToolResult:
    ctx = ToolContext(user=DEMO_USERS[role], session=session_scope, thread_id="t-perm")
    return run_tool(TOOLS[name], ctx, args, lambda *_: None)


@pytest.fixture
def manager_customer(tracker: Tracker) -> Iterator[str]:
    """主管自己名下的客户（用例结束后连同子数据一起清理）。"""
    name = f"测试主管客户-{uuid.uuid4().hex[:6]}"
    with session_scope() as db:
        customer = Customer(name=name, level="C", owner_id=MANAGER.id, team_id=MANAGER.team_id)
        db.add(customer)
        db.flush()
        cid = customer.id
    yield str(cid)
    tracker.purge()
    with session_scope() as db:
        tracker.followups = list(db.scalars(select(Followup.id).where(Followup.customer_id == cid)))
    tracker.purge()
    with session_scope() as db:
        db.execute(delete(Activity).where(Activity.subject_id == cid))
        db.execute(delete(Customer).where(Customer.id == cid))


# ---------- 管理员：业务数据只读 ----------


def test_admin_cannot_write_customer_or_followup(client: TestClient) -> None:
    r = client.post("/api/customers", json={"name": f"管理员-{uuid.uuid4().hex}"}, headers=ADMIN_H)
    assert r.status_code == 403
    assert_forbidden(r, "role_forbidden")
    body = {"type": "phone", "content": "管理员跟进"}
    assert_forbidden(
        client.post(f"/api/customers/{C_MINGLI}/followups", json=body, headers=ADMIN_H),
        "role_forbidden",
    )


def test_admin_cannot_write_opportunity(client: TestClient, tracker: Tracker) -> None:
    body = {"customer_id": str(C_MINGLI), "name": "管理员商机", "amount": 1}
    assert_forbidden(
        client.post("/api/opportunities", json=body, headers=ADMIN_H), "role_forbidden"
    )
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}"
    assert_forbidden(client.patch(url, json={"amount": 1}, headers=ADMIN_H), "role_forbidden")
    assert_forbidden(
        client.patch(f"{url}/stage", json={"stage": "qualified"}, headers=ADMIN_H),
        "role_forbidden",
    )


def test_admin_cannot_act_on_quote(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD))
    assert_forbidden(act(client, qid, "submit", ADMIN_H), "role_forbidden")
    assert act(client, qid, "submit")["data"]["status"] == "approved"
    assert_forbidden(act(client, qid, "send", ADMIN_H), "role_forbidden")
    assert act(client, qid, "send")["data"]["status"] == "sent"
    for action in ("accept", "reject"):
        assert_forbidden(act(client, qid, action, ADMIN_H), "role_forbidden")


def test_admin_cannot_write_expense(client: TestClient, tracker: Tracker) -> None:
    body = {"type": "transport", "amount": 100, "headcount": 1, "occurred_on": "2026-10-24",
            "reason": "管理员报销"}  # fmt: skip
    assert_forbidden(client.post("/api/expenses", json=body, headers=ADMIN_H), "role_forbidden")
    eid = new_expense(client, tracker)["id"]
    files = {"file": ("发票.pdf", PDF, "application/pdf")}
    up = client.post(
        f"/api/expenses/{eid}/attachments", files=files, data={"kind": "invoice"}, headers=ADMIN_H
    )
    assert_forbidden(up, "role_forbidden")
    assert_forbidden(client.post(f"/api/expenses/{eid}/submit", headers=ADMIN_H), "role_forbidden")


def test_admin_and_sales_cannot_register_payment(client: TestClient, tracker: Tracker) -> None:
    contract = _accepted_contract(client, tracker)
    url = f"/api/contracts/{contract['id']}/payments"
    assert_forbidden(client.post(url, json={"amount": 1}, headers=ADMIN_H), "role_forbidden")
    assert_forbidden(client.post(url, json={"amount": 1}, headers=SALES_H), "role_forbidden")
    paid = client.post(url, json={"amount": 1}, headers=MANAGER_H).json()
    assert paid["code"] == 0 and paid["data"]["paid_amount"] == 1


# ---------- 主管：看得到但不能改销售的记录 ----------


def test_manager_cannot_modify_sales_records(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}"
    assert_forbidden(client.patch(url, json={"amount": 1}, headers=MANAGER_H), "not_owner")
    stage = {"stage": "qualified"}
    assert_forbidden(client.patch(f"{url}/stage", json=stage, headers=MANAGER_H), "not_owner")
    qid = create_quote(tracker, make_tier(GOOD))
    assert_forbidden(act(client, qid, "submit", MANAGER_H), "not_owner")
    eid = new_expense(client, tracker)["id"]
    with_receipts(client, eid)
    assert_forbidden(client.post(f"/api/expenses/{eid}/submit", headers=MANAGER_H), "not_owner")
    files = {"file": ("小票.png", PNG, "image/png")}
    up = client.post(
        f"/api/expenses/{eid}/attachments", files=files, data={"kind": "other"}, headers=MANAGER_H
    )
    assert_forbidden(up, "not_owner")
    att = client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]["attachments"][0]
    assert_forbidden(client.delete(f"/api/attachments/{att['id']}", headers=MANAGER_H), "not_owner")


def test_manager_cannot_create_under_sales_parent(client: TestClient) -> None:
    body = {"customer_id": str(C_MINGLI), "name": "主管越权商机", "amount": 1}
    assert_forbidden(client.post("/api/opportunities", json=body, headers=MANAGER_H), "not_owner")
    followup = {"type": "phone", "content": "主管越权跟进"}
    r = client.post(f"/api/customers/{C_MINGLI}/followups", json=followup, headers=MANAGER_H)
    assert_forbidden(r, "not_owner")
    expense = {"type": "transport", "amount": 100, "headcount": 1, "occurred_on": "2026-10-24",
               "reason": "x", "opportunity_id": str(OPP_MINGLI)}  # fmt: skip
    assert_forbidden(client.post("/api/expenses", json=expense, headers=MANAGER_H), "not_owner")


def test_manager_owns_records_normally(
    client: TestClient, tracker: Tracker, manager_customer: str
) -> None:
    body = {"customer_id": manager_customer, "name": "主管商机", "amount": 1_000_000}
    opp = client.post("/api/opportunities", json=body, headers=MANAGER_H).json()["data"]
    tracker.opportunities.append(uuid.UUID(opp["id"]))
    assert opp["owner"]["name"] == "李薇"
    url = f"/api/opportunities/{opp['id']}/stage"
    assert client.patch(url, json={"stage": "qualified"}, headers=MANAGER_H).json()["code"] == 0
    fu = {"type": "visit", "content": "主管拜访"}
    r = client.post(f"/api/customers/{manager_customer}/followups", json=fu, headers=MANAGER_H)
    assert r.json()["code"] == 0
    qid = create_quote(tracker, make_tier(GOOD), opp["id"], user=MANAGER)
    for action, status in (("submit", "approved"), ("send", "sent")):
        assert act(client, qid, action, MANAGER_H)["data"]["status"] == status
    # 销售看不到主管的报价（40401），也就不能操作
    assert act(client, qid, "accept")["code"] == 40401


def test_manager_own_expense(client: TestClient, tracker: Tracker) -> None:
    body = {"type": "transport", "amount": 10_000, "headcount": 1, "occurred_on": "2026-10-24",
            "reason": "测试-主管差旅"}  # fmt: skip
    r = client.post("/api/expenses", json=body, headers=MANAGER_H).json()
    assert r["code"] == 0
    eid = r["data"]["id"]
    tracker.expenses.append(uuid.UUID(eid))
    files = {"file": ("发票.pdf", PDF, "application/pdf")}
    up = client.post(
        f"/api/expenses/{eid}/attachments", files=files, data={"kind": "invoice"}, headers=MANAGER_H
    )
    assert up.json()["code"] == 0
    submitted = client.post(f"/api/expenses/{eid}/submit", headers=MANAGER_H).json()
    assert submitted["code"] == 0 and submitted["data"]["status"] == "approved"


def test_manager_approves_team_quote(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(LOW))
    assert act(client, qid, "submit")["data"]["status"] == "pending_approval"
    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H).json()
    aid = next(a["id"] for a in pending["data"]["items"] if a["target"]["id"] == qid)
    decide = f"/api/approvals/{aid}/decide"
    assert_forbidden(
        client.post(decide, json={"decision": "approve"}, headers=ADMIN_H), "role_forbidden"
    )
    r = client.post(decide, json={"decision": "approve"}, headers=MANAGER_H).json()
    assert r["code"] == 0 and r["data"]["status"] == "approved"


# ---------- Agent 工具 ----------


def test_admin_agent_write_tools_return_structured_error(
    client: TestClient, tracker: Tracker
) -> None:
    opp = new_opp(client, tracker)
    calls = {
        "add_followup": {"customer_id": str(C_MINGLI), "content": "管理员跟进"},
        "update_opportunity_stage": {"opportunity_id": opp["id"], "stage": "qualified",
                                     "idempotency_key": uuid.uuid4().hex},
        "submit_expense": {"amount": 100, "occurred_on": date(2026, 10, 24).isoformat(),
                           "reason": "x", "idempotency_key": uuid.uuid4().hex},
        "generate_quote": {"pack_id": "llm_deploy", "tier": make_tier(GOOD).model_dump(),
                           "idempotency_key": uuid.uuid4().hex},
        "decide_approval": {"approval_id": str(uuid.uuid4()), "decision": "approve"},
    }  # fmt: skip
    for name, args in calls.items():
        res = _call(Role.ADMIN, name, args)
        assert not res.ok and res.error is not None, name
        assert res.error["code"] == 40301 and res.error["data"]["rule"] == "role_forbidden", name
    assert _call(Role.ADMIN, "pipeline_summary", {}).ok
    assert _call(Role.ADMIN, "search_customer", {"keyword": "明理"}).ok


def test_manager_agent_cannot_touch_sales_records(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    args = {"opportunity_id": opp["id"], "stage": "qualified", "idempotency_key": "k"}
    res = _call(Role.MANAGER, "update_opportunity_stage", args)
    assert res.error is not None and res.error["data"]["rule"] == "not_owner"
    quote = {"pack_id": "llm_deploy", "tier": make_tier(GOOD).model_dump(),
             "opportunity_id": opp["id"], "idempotency_key": uuid.uuid4().hex}  # fmt: skip
    res = _call(Role.MANAGER, "generate_quote", quote)
    assert res.error is not None and res.error["data"]["rule"] == "not_owner"
