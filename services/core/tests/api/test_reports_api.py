"""销售日报：事实来自当天操作、草稿（模板 / 剧本模型）、保存提交、团队视图与汇总、权限。"""

import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import delete

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import DailyReport
from app.crm.services import report_service
from app.crm.services.codes import local_today
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.scripted_llm import ScriptedModel

SALES = DEMO_USERS[Role.SALES]


@pytest.fixture(autouse=True)
def clean_reports() -> Iterator[None]:
    def wipe() -> None:
        with session_scope() as db:
            db.execute(delete(DailyReport).where(DailyReport.report_date >= local_today()))

    wipe()
    yield
    wipe()


def _followup(client: TestClient, tracker: Tracker, content: str) -> str:
    name = f"日报客户-{uuid.uuid4().hex[:6]}"
    cid = client.post("/api/customers", json={"name": name, "level": "B"}, headers=SALES_H).json()[
        "data"
    ]["id"]
    tracker.customers.append(uuid.UUID(cid))
    r = client.post(
        f"/api/customers/{cid}/followups",
        json={"type": "visit", "content": content},
        headers=SALES_H,
    )
    assert r.json()["code"] == 0
    return name


def test_facts_from_today_actions(client: TestClient, tracker: Tracker) -> None:
    name = _followup(client, tracker, "演示了合同审查，客户要报价")
    data = client.get("/api/reports/daily", headers=SALES_H).json()["data"]
    assert data["status"] == "none"
    facts = data["facts"]
    assert facts["stats"]["followups"] >= 1
    assert any(name in f and "客户要报价" in f for f in facts["followups"])
    assert any(a.startswith("记录跟进") for a in facts["actions"])


def test_template_draft_and_save_submit(client: TestClient, tracker: Tracker) -> None:
    name = _followup(client, tracker, "客户预算待定")
    with session_scope() as db:
        out = report_service.draft_daily(db, SALES, local_today(), None)
    assert out.source == "template"
    assert "【今日概况】" in out.content and name in out.content

    body = {"date": str(local_today()), "content": out.content}
    saved = client.put("/api/reports/daily", json=body, headers=SALES_H).json()["data"]
    assert saved["status"] == "draft" and saved["submitted_at"] is None
    # 草稿时主管看不到内容
    team = client.get("/api/reports/team", headers=MANAGER_H).json()["data"]
    me = next(m for m in team["members"] if m["user_id"] == str(SALES.id))
    assert me["status"] == "draft" and me["content"] is None

    submitted = client.put(
        "/api/reports/daily", json={**body, "submit": True}, headers=SALES_H
    ).json()["data"]
    assert submitted["status"] == "submitted" and submitted["submitted_at"]
    team = client.get("/api/reports/team", headers=MANAGER_H).json()["data"]
    me = next(m for m in team["members"] if m["user_id"] == str(SALES.id))
    assert me["content"] == out.content.strip() and team["submitted"] >= 1
    assert team["members"][0]["status"] == "submitted"  # 已提交排在前面


def test_ai_draft_uses_facts(tracker: Tracker, client: TestClient) -> None:
    _followup(client, tracker, "李总确认下周三签约")
    llm = ScriptedModel(script=[AIMessage(content="【今日概况】\n- 跟进 1 次")])
    with session_scope() as db:
        out = report_service.draft_daily(db, SALES, local_today(), llm)
    assert out.source == "ai" and out.content.startswith("【今日概况】")
    assert "李总确认下周三签约" in llm.seen[0][-1].content


def test_permissions_and_date_range(client: TestClient) -> None:
    assert client.get("/api/reports/team", headers=SALES_H).json()["code"] == 40301
    assert client.get("/api/reports/daily", headers=ADMIN_H).json()["code"] == 40301
    future = str(local_today() + timedelta(days=1))
    r = client.get("/api/reports/daily", params={"date": future}, headers=SALES_H).json()
    assert r["code"] == 40001
    assert client.get("/api/reports/team", headers=ADMIN_H).json()["code"] == 0


def test_team_summary_template(client: TestClient, tracker: Tracker) -> None:
    _followup(client, tracker, "推进中")
    client.put(
        "/api/reports/daily",
        json={"date": str(local_today()), "content": "今天跟进了一家客户", "submit": True},
        headers=SALES_H,
    )
    with session_scope() as db:
        out = report_service.team_summary(db, DEMO_USERS[Role.MANAGER], 7, None)
    assert out.source == "template"
    assert SALES.name in out.content and "提交 1 天" in out.content
    r = client.post("/api/reports/team/summary", json={"days": 7}, headers=MANAGER_H).json()
    assert r["code"] == 0 and r["data"]["content"]
