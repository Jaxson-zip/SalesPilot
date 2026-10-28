"""外部情报：演示数据标注、同一客户结果稳定、可见范围、未接入的数据源、AI 工具。"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.agent.tools import TOOLS, ToolContext
from app.common.auth import Role
from app.common.config import get_settings
from app.common.db import session_scope
from app.crm.services.codes import local_today
from app.crm.services.demo import DEMO_USERS
from app.crm.services.intel_service import SIGNAL_DAYS, DemoProvider, _signals
from tests.api.conftest import SALES2_H, SALES_H, Tracker


def _customer(client: TestClient, tracker: Tracker) -> str:
    body = {"name": f"情报测试-{uuid.uuid4().hex[:6]}", "level": "B", "industry": "律所"}
    cid = client.post("/api/customers", json=body, headers=SALES_H).json()["data"]["id"]
    tracker.customers.append(uuid.UUID(cid))
    return cid


def test_demo_intel_is_labeled_and_stable(client: TestClient, tracker: Tracker) -> None:
    cid = _customer(client, tracker)
    a = client.get(f"/api/customers/{cid}/intel", headers=SALES_H).json()["data"]
    b = client.get(f"/api/customers/{cid}/intel", headers=SALES_H).json()["data"]
    assert a["demo"] is True and "不是真实" in a["notice"]
    assert a["profile"] == b["profile"] and a["tenders"] == b["tenders"]
    assert a["profile"]["industry"] == "律所"
    assert len(a["tenders"]) == 3 and a["news"]
    assert client.get(f"/api/customers/{cid}/intel", headers=SALES2_H).json()["code"] == 40401


def test_opportunity_tenders_become_signals() -> None:
    p = DemoProvider()
    for i in range(30):  # 找一个有相关招标的名字
        _, news, tenders, _ = p.lookup(f"样例客户{i}", None)
        hits = [t for t in tenders if t.opportunity and t.kind != "中标"]
        recent = [t for t in hits if (local_today() - t.date).days <= SIGNAL_DAYS]
        if recent:
            signals = _signals(news, tenders, local_today())
            assert any(recent[0].title in s for s in signals)
            break
    else:
        pytest.fail("demo data never produced a relevant tender")


def test_unknown_provider(
    client: TestClient, tracker: Tracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _customer(client, tracker)
    monkeypatch.setattr(get_settings(), "intel_provider", "qichacha")
    r = client.get(f"/api/customers/{cid}/intel", headers=SALES_H).json()
    assert r["code"] == 50201 and "未接入" in r["message"]


def test_intel_tool_marks_demo(client: TestClient, tracker: Tracker) -> None:
    cid = _customer(client, tracker)
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope)
    spec = TOOLS["get_company_intel"]
    result = spec.func(ctx, spec.args_model(customer_id=uuid.UUID(cid)))
    assert result.ok and "演示数据" in result.summary and result.data["demo"] is True
