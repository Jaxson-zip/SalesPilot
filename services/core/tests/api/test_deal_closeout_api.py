"""用户复测：输单收尾、草稿补关联客户、审批后撤回修改 / 复制新版本。"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Approval, Quote, Task
from app.crm.services import quote_service
from app.crm.services.demo import DEMO_USERS
from seed.data import C_MINGLI
from tests.api.conftest import SALES_H, Tracker, make_tier
from tests.api.test_opportunities_api import new_opp
from tests.api.test_quotes_contracts_api import GOOD, LOW, act, create_quote


def _lose(client: TestClient, opp_id: str) -> dict:
    body = {"stage": "lost", "lost_reason": "客户取消项目"}
    url = f"/api/opportunities/{opp_id}/stage"
    return client.patch(url, json=body, headers=SALES_H).json()


def test_lost_closes_quotes_tasks_and_suggestions(client: TestClient, tracker: Tracker) -> None:
    """回归：输单后关联报价还能提交并自动通过，商机仍提示「报价已审批，还没发给客户」。"""
    opp = new_opp(client, tracker)
    approved = create_quote(tracker, make_tier(GOOD), opp["id"])
    act(client, approved, "submit")
    pending = create_quote(tracker, make_tier(LOW), opp["id"])
    assert act(client, pending, "submit")["data"]["status"] == "pending_approval"
    draft = create_quote(tracker, make_tier(GOOD), opp["id"])
    task = {"title": "回访", "due_at": "2026-12-01T10:00:00+08:00"}
    task |= {"subject_type": "opportunity", "subject_id": opp["id"]}
    assert client.post("/api/tasks", json=task, headers=SALES_H).json()["code"] == 0

    assert _lose(client, opp["id"])["code"] == 0
    with session_scope() as db:
        ids = [uuid.UUID(q) for q in (approved, pending, draft)]
        assert {db.get(Quote, i).status for i in ids} == {"closed"}  # type: ignore[union-attr]
        stmt = select(Approval.status).where(Approval.target_id == uuid.UUID(pending))
        assert db.scalars(stmt).all() == ["rejected"]
        tasks = select(Task.done).where(Task.subject_id == uuid.UUID(opp["id"]))
        assert all(db.scalars(tasks).all())
    submit = act(client, draft, "submit")
    assert submit["code"] == 42201
    url = f"/api/opportunities/{opp['id']}/suggestions"
    assert client.get(url, headers=SALES_H).json()["data"] == []
    # 输单商机不能再出报价
    body = {"opportunity_id": opp["id"], "pack": "llm_deploy", "items": [{"sku": "x", "qty": 1}]}
    created = client.post("/api/quotes", json=body, headers=SALES_H).json()
    assert created["code"] == 42201 and created["data"]["rule"] == "opportunity_lost"


def test_draft_without_customer_can_link_then_submit(client: TestClient, tracker: Tracker) -> None:
    """回归：AI 报价没识别出客户，草稿没有补关联入口，只能重新生成。"""
    with session_scope() as db:
        out = quote_service.create_from_tier(
            db, DEMO_USERS[Role.SALES], pack="llm_deploy", tier=make_tier(GOOD),
            opportunity_id=None, idempotency_key=f"test:{uuid.uuid4().hex}",
        )  # fmt: skip
    tracker.quotes.append(out.id)
    qid = str(out.id)
    assert act(client, qid, "submit")["code"] == 42201
    url = f"/api/quotes/{qid}/link"
    assert client.patch(url, json={}, headers=SALES_H).json()["code"] == 40001
    linked = client.patch(url, json={"customer_id": str(C_MINGLI)}, headers=SALES_H).json()
    assert linked["data"]["customer"]["id"] == str(C_MINGLI)
    assert linked["data"]["total_price"] == out.total_price  # 明细和价格不动
    assert act(client, qid, "submit")["data"]["status"] == "approved"
    again = client.patch(url, json={"customer_id": str(C_MINGLI)}, headers=SALES_H).json()
    assert again["code"] == 42201  # 提交后不能再改关联


def test_revise_approved_and_copy_sent_as_new_version(client: TestClient, tracker: Tracker) -> None:
    """回归：审批后没有撤回修改或复制修订的路径，发现漏项只能重新建单。"""
    qid = create_quote(tracker, make_tier(GOOD))
    act(client, qid, "submit")
    revised = act(client, qid, "revise")["data"]
    assert revised["status"] == "draft"
    assert act(client, qid, "revise")["code"] == 42201  # 草稿不用撤回
    act(client, qid, "submit")
    assert act(client, qid, "send")["data"]["status"] == "sent"

    copy = client.post(f"/api/quotes/{qid}/revisions", headers=SALES_H).json()["data"]
    tracker.quotes.append(uuid.UUID(copy["id"]))
    assert copy["status"] == "draft" and copy["revision_of"]["code"]
    assert len(copy["items"]) == 2
    dup = client.post(f"/api/quotes/{qid}/revisions", headers=SALES_H).json()
    assert dup["code"] == 42201  # 已有修订中的新版本
    act(client, copy["id"], "submit")
    act(client, copy["id"], "send")
    old = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert old["status"] == "closed" and old["revisions"][0]["id"] == copy["id"]
    assert act(client, qid, "accept")["code"] == 42201  # 旧版本不能再成交
