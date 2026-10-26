"""站内通知（审批触发、已读）与报销参与人结构化（接口契约 v3 §15、§17）。"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.common.db import session_scope
from app.crm.models import Expense
from app.crm.services.demo import demo_id
from seed.data import C_HNZZ, C_MINGLI, MANAGER
from tests.api.conftest import MANAGER_H, SALES_H, Tracker, make_tier
from tests.api.test_quotes_contracts_api import LOW, act, create_quote

WANG = str(demo_id("contact:mingli:wang"))
CHEN = str(demo_id("contact:mingli:chen"))
LIU = str(demo_id("contact:hnzz:liu"))  # 华南智能制造的联系人
ADMIN_ID = str(demo_id("user:admin"))
SALES_ID = str(demo_id("user:sales"))


def notifications(client: TestClient, headers: dict[str, str], unread: bool = False) -> dict:
    url = f"/api/notifications?limit=100{'&unread=true' if unread else ''}"
    return client.get(url, headers=headers).json()["data"]


# ---------- §15 通知 ----------


def test_approval_notifications(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(LOW))
    submitted = act(client, qid, "submit")["data"]
    pending = [
        n
        for n in notifications(client, MANAGER_H)["items"]
        if n["type"] == "approval_pending" and submitted["code"] in n["title"]
    ]
    assert len(pending) == 1 and pending[0]["link"] == "/approvals" and not pending[0]["read"]
    assert "毛利" in pending[0]["body"]
    approval_id = submitted["approvals"][0]["id"]
    decided = client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"decision": "reject", "comment": "补充服务项"},
        headers=MANAGER_H,
    )
    assert decided.json()["code"] == 0
    mine = [
        n
        for n in notifications(client, SALES_H)["items"]
        if n["type"] == "approval_decided" and submitted["code"] in n["title"]
    ]
    assert len(mine) == 1 and "驳回" in mine[0]["title"] and mine[0]["body"] == "补充服务项"
    assert mine[0]["link"] == f"/quotes/{qid}"


def test_mark_read(client: TestClient) -> None:
    data = notifications(client, MANAGER_H, unread=True)
    assert data["unread"] >= 2 and data["total"] == data["unread"]
    first = data["items"][0]["id"]
    r = client.post("/api/notifications/read", json={"ids": [first]}, headers=MANAGER_H).json()
    assert r["data"] == {"updated": 1, "unread": data["unread"] - 1}
    # 别人的通知 id 会被忽略
    other = client.post("/api/notifications/read", json={"ids": [first]}, headers=SALES_H)
    assert other.json()["data"]["updated"] == 0
    everything = client.post("/api/notifications/read", json={}, headers=MANAGER_H).json()
    assert everything["data"]["unread"] == 0
    assert notifications(client, MANAGER_H, unread=True)["items"] == []
    assert notifications(client, MANAGER_H)["total"] >= 2  # 已读的仍在全部列表里


def test_notification_validation(client: TestClient) -> None:
    assert client.get("/api/notifications?limit=0", headers=SALES_H).json()["code"] == 40001
    bad = client.post("/api/notifications/read", json={"ids": ["x"]}, headers=SALES_H)
    assert bad.json()["code"] == 40001
    assert client.get("/api/notifications").json()["code"] == 40101


# ---------- §17 报销参与人 ----------


def create(client: TestClient, tracker: Tracker, **extra: object) -> dict:
    body = {
        "type": "entertainment",
        "amount": 90_000,
        "occurred_on": "2026-10-24",
        "customer_id": str(C_MINGLI),
        "reason": "测试-参与人",
        "contact_ids": [WANG],
        "idempotency_key": uuid.uuid4().hex,
        **extra,
    }
    r = client.post("/api/expenses", json=body, headers=SALES_H).json()
    if r["code"] == 0:
        tracker.expenses.append(uuid.UUID(r["data"]["id"]))
    return r


def test_headcount_and_participants_computed(client: TestClient, tracker: Tracker) -> None:
    r = create(
        client,
        tracker,
        contact_ids=[WANG, CHEN, WANG],
        extra_guests=1,
        headcount=10,
        colleague_ids=[str(MANAGER.id), SALES_ID],
        participants="客户端写的会被忽略",
    )
    data = r["data"]
    assert data["headcount"] == 5  # 2 联系人 + 1 同事 + 本人 + 1 其他（客户端的 10 被忽略）
    assert data["participants"] == "客户：王律师、陈工；我方：张晨、李薇；其他 1 人"
    assert [c["name"] for c in data["contacts"]] == ["王律师", "陈工"]
    assert data["contacts"][0]["title"] == "管理合伙人"
    assert data["colleagues"] == [{"id": str(MANAGER.id), "name": "李薇"}]
    assert data["extra_guests"] == 1
    assert data["policy_check"]["per_person"] == 18_000  # ¥900 / 5 人


def test_participant_validation(client: TestClient, tracker: Tracker) -> None:
    no_customer = create(client, tracker, customer_id=None)
    assert no_customer["code"] == 40001
    assert no_customer["data"]["errors"][0]["loc"] == ["body", "customer_id"]
    no_contact = create(client, tracker, contact_ids=[])
    assert no_contact["code"] == 40001
    assert no_contact["data"]["errors"][0]["loc"] == ["body", "contact_ids"]
    other_customer = create(client, tracker, contact_ids=[LIU])
    assert other_customer["code"] == 40001
    not_team = create(client, tracker, colleague_ids=[ADMIN_ID])
    assert not_team["code"] == 40001
    negative = create(client, tracker, extra_guests=-1)
    assert negative["code"] == 40001
    # 非招待类不要求联系人；但选了联系人就必须关联客户
    transport = create(client, tracker, type="transport", contact_ids=[], customer_id=None)
    assert transport["code"] == 0 and transport["data"]["headcount"] == 1
    orphan = create(client, tracker, type="transport", contact_ids=[LIU], customer_id=None)
    assert orphan["code"] == 40001
    hnzz = create(client, tracker, type="transport", contact_ids=[LIU], customer_id=str(C_HNZZ))
    assert hnzz["code"] == 0 and hnzz["data"]["participants"] == "客户：刘经理；我方：张晨"


def test_legacy_expense_returns_empty_arrays(client: TestClient, tracker: Tracker) -> None:
    eid = create(client, tracker)["data"]["id"]
    with session_scope() as db:
        db.execute(
            update(Expense)
            .where(Expense.id == uuid.UUID(eid))
            .values(contact_ids=None, colleague_ids=None, extra_guests=None)
        )
    data = client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]
    assert data["contacts"] == [] and data["colleagues"] == [] and data["extra_guests"] == 0
