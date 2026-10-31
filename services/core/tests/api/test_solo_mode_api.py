"""个人模式（一个人接单）：审批规则触发时自动通过并记下原因；主管可以改系统配置，成员管理仍只有管理员。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.db import session_scope
from app.crm.models import Activity
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker, make_tier
from tests.api.test_expenses_approvals_api import new_expense, with_receipts
from tests.api.test_quotes_contracts_api import LOW, act, create_quote


def _set_solo(client: TestClient, value: bool | None) -> None:
    body = {"values": {"org.solo_mode": value}}
    assert client.put("/api/settings/rules", json=body, headers=ADMIN_H).json()["code"] == 0


@pytest.fixture
def solo(client: TestClient) -> Iterator[None]:
    _set_solo(client, True)
    yield
    _set_solo(client, None)  # 恢复默认（团队模式）


def test_team_mode_by_default(client: TestClient) -> None:
    me = client.get("/api/me", headers=MANAGER_H).json()["data"]
    assert me["solo_mode"] is False
    assert client.get("/api/settings/rules", headers=MANAGER_H).json()["code"] == 40301
    data = client.get("/api/settings/rules", headers=ADMIN_H).json()["data"]
    field = next(f for f in data["fields"] if f["key"] == "org.solo_mode")
    assert field["kind"] == "bool" and field["value"] is False


@pytest.mark.usefixtures("solo")
def test_manager_configures_but_not_members(client: TestClient) -> None:
    assert client.get("/api/me", headers=MANAGER_H).json()["data"]["solo_mode"] is True
    assert client.get("/api/settings/rules", headers=MANAGER_H).json()["code"] == 0
    assert client.get("/api/admin/jobs", headers=MANAGER_H).json()["code"] == 0
    assert client.get("/api/admin/users", headers=MANAGER_H).json()["code"] == 40301
    assert client.get("/api/settings/rules", headers=SALES_H).json()["code"] == 40301


@pytest.mark.usefixtures("solo")
def test_low_margin_quote_skips_approval(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(LOW))
    data = act(client, qid, "submit")["data"]
    assert data["status"] == "approved" and data["approvals"] == []
    with session_scope() as db:
        notes = db.scalars(select(Activity.content).where(Activity.subject_id == uuid.UUID(qid)))
        assert any("个人模式免审批" in c and "毛利" in c for c in notes)  # 原因照常记下


@pytest.mark.usefixtures("solo")
def test_over_limit_expense_skips_approval(client: TestClient, tracker: Tracker) -> None:
    eid = new_expense(client, tracker, amount=86_000)["id"]
    with_receipts(client, eid)
    data = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()["data"]
    assert data["status"] == "approved"
    assert data["over_limit"]  # 超标照常标出来
