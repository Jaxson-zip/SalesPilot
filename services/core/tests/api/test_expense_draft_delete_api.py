"""删除报销草稿、审批流转信息（用户反馈：草稿删不掉、审批进度不透明、「其他」类为何要审批）。"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common import storage
from app.common.db import session_scope
from app.crm.models import Attachment
from app.crm.services.rule_notes import expense_note
from app.rules.loader import load_rules
from tests.api.conftest import MANAGER_H, SALES2_H, SALES_H, Tracker
from tests.api.test_expenses_approvals_api import new_expense, with_receipts


def _storage_keys(eid: str) -> list[str]:
    with session_scope() as db:
        rows = db.scalars(
            select(Attachment.storage_key).where(Attachment.owner_ref_id == uuid.UUID(eid))
        )
        return list(rows)


def test_delete_draft_removes_files(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker)["id"]
    with_receipts(client, eid)
    keys = _storage_keys(eid)
    assert len(keys) == 2 and all(storage.path_of(k).exists() for k in keys)
    # 别人的草稿看不到
    assert client.delete(f"/api/expenses/{eid}", headers=SALES2_H).json()["code"] == 40401
    assert client.delete(f"/api/expenses/{eid}", headers=SALES_H).json()["code"] == 0
    assert client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["code"] == 40401
    assert _storage_keys(eid) == [] and not any(storage.path_of(k).exists() for k in keys)


def test_delete_submitted_expense_rejected(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker, amount=86_000)["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    body = client.delete(f"/api/expenses/{eid}", headers=SALES_H).json()
    assert body["code"] == 42201 and body["data"]["status"] == "pending_approval"


def test_pending_approval_shows_handler_and_time(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker, amount=86_000)["id"]
    with_receipts(client, eid)
    client.post(f"/api/expenses/{eid}/submit", headers=SALES_H)
    a = client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]["approvals"][-1]
    assert a["status"] == "pending" and a["handler"]["name"] == "李薇" and a["submitted_at"]
    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H)
    aid = next(x["id"] for x in pending.json()["data"]["items"] if x["target"]["id"] == eid)
    client.post(f"/api/approvals/{aid}/decide", json={"decision": "approve"}, headers=MANAGER_H)
    done = client.get(f"/api/expenses/{eid}", headers=SALES_H).json()["data"]["approvals"][-1]
    # 处理完后显示审批人，不再显示「待谁处理」
    assert done["handler"] is None and done["approver"]["name"] == "李薇" and done["decided_at"]


def test_other_type_note_explains_always_needs_approval(client: TestClient) -> None:
    notes = str(expense_note(load_rules()).items)
    assert "其他费用" in notes and "每笔都需主管审批" in notes
    templates = client.get("/api/templates", headers=SALES_H).json()["data"]
    assert "不论金额大小" in str(templates)
