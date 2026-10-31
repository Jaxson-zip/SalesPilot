"""接口测试（不需要数据库）：health、docs、假登录、/api/me、角色限制、规则接口、Agent SSE。"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import service
from app.common.auth import Role
from tests.conftest import auth_header


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0 and body["data"]["status"] in {"ok", "degraded"}
    assert isinstance(body["data"]["db"], bool)


def test_openapi_and_docs(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/auth/mock-login", "/api/me", "/api/customers", "/api/agent/chat"} <= set(paths)


@pytest.mark.parametrize("role", ["sales", "manager", "admin"])
def test_mock_login(client: TestClient, role: str) -> None:
    r = client.post("/api/auth/mock-login", json={"role": role})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["token"] and data["user"]["role"] == role
    assert set(data["user"]) == {
        "id", "name", "role", "team_id", "team_name", "username", "must_change_password",
    }  # fmt: skip


def test_mock_login_invalid_role(client: TestClient) -> None:
    r = client.post("/api/auth/mock-login", json={"role": "root"})
    assert r.status_code == 400 and r.json()["code"] == 40001


def test_me(client: TestClient) -> None:
    token = client.post("/api/auth/mock-login", json={"role": "sales"}).json()["data"]["token"]
    r = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["data"]["name"] == "张晨"


@pytest.mark.parametrize("header", [{}, {"Authorization": "Bearer bad"}])
def test_me_unauthorized(client: TestClient, header: dict[str, str]) -> None:
    r = client.get("/api/me", headers=header)
    assert r.status_code == 401 and r.json()["code"] == 40101


def test_approvals_forbidden_for_sales(client: TestClient) -> None:
    r = client.get("/api/approvals", headers=auth_header(Role.SALES))
    assert r.status_code == 403 and r.json()["code"] == 40301


def test_packs(client: TestClient) -> None:
    r = client.get("/api/packs", headers=auth_header(Role.ADMIN))
    assert {p["id"] for p in r.json()["data"]} >= {"llm_deploy", "it_office"}


def test_commission_estimate(client: TestClient) -> None:
    """提成试算只给 AI「算提成」用，不单独开放 REST 接口（界面上没有入口）。"""
    from app.crm.schemas.finance import CommissionEstimateIn
    from app.crm.services import finance_service

    body = {"lines": [{"category": "hardware", "amount": 10_000_000}], "margin_rate": 0.2}
    result = finance_service.estimate_commission(CommissionEstimateIn(**body))
    assert result.estimated == 150_000 and result.halved
    r = client.post("/api/commissions/estimate", json=body, headers=auth_header(Role.SALES))
    assert r.status_code == 404


def test_expense_precheck(client: TestClient) -> None:
    body = {"type": "entertainment", "amount": 86_000, "headcount": 4, "occurred_on": "2026-10-24"}
    r = client.post("/api/expenses/precheck", json=body, headers=auth_header(Role.SALES))
    assert r.json()["data"]["need_approval"] and r.json()["data"]["over_amount"] == 26_000
    bad = client.post(
        "/api/expenses/precheck", json={**body, "amount": 0}, headers=auth_header(Role.SALES)
    )
    assert bad.json()["code"] == 40001


@pytest.fixture
def offline_agent(monkeypatch: pytest.MonkeyPatch, fake_quotes: None) -> None:
    monkeypatch.setattr(service, "make_pack_resolver", lambda user: lambda _opp: "llm_deploy")
    monkeypatch.setattr(service, "get_chat_model", lambda *a, **k: None)
    monkeypatch.setattr(service, "model_available", lambda *a, **k: False)


def test_agent_chat_and_resume_sse(
    client: TestClient, offline_agent: None, sse_parser: Any
) -> None:
    headers = auth_header(Role.SALES)
    body = {"thread_id": "api-t1", "message": "给明理律所出 Qwen3-32B 方案，50 人并发"}
    r = client.post("/api/agent/chat", json=body, headers=headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = sse_parser(r.text)
    assert [e for e, _ in events][-2:] == ["interrupt", "done"]

    r = client.post(
        "/api/agent/resume", json={"thread_id": "api-t1", "decision": "approve"}, headers=headers
    )
    events = sse_parser(r.text)
    assert ("artifact", "quote") in [(e, d.get("type")) for e, d in events]
    assert events[-1] == ("done", {"thread_id": "api-t1"})


def test_agent_resume_unknown_thread(client: TestClient, offline_agent: None) -> None:
    r = client.post(
        "/api/agent/resume",
        json={"thread_id": "nope", "decision": "approve"},
        headers=auth_header(Role.SALES),
    )
    assert r.status_code == 404 and r.json()["code"] == 40401


def test_agent_chat_requires_login(client: TestClient) -> None:
    r = client.post("/api/agent/chat", json={"thread_id": "t", "message": "hi"})
    assert r.json()["code"] == 40101


def test_agent_chat_validation(client: TestClient) -> None:
    r = client.post(
        "/api/agent/chat", json={"thread_id": "t", "message": ""}, headers=auth_header(Role.SALES)
    )
    assert r.json()["code"] == 40001


GATEWAY_CARDS = [
    {"id": "deepseek-chat", "type": "model", "available": True, "capabilities": {"tools": True}},
    {"id": "hunyuan-turbo", "type": "model", "available": False, "capabilities": {"tools": True}},
    {"id": "embed", "type": "model", "available": True, "capabilities": {"embeddings": True}},
    {
        "id": "chat-agent",
        "type": "group",
        "available": True,
        "members": ["deepseek-chat", "hunyuan-turbo"],
        "capabilities": {"tools": True},
    },
]


def test_agent_models_lists_tool_capable_models(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.agent import models

    monkeypatch.setattr(models, "list_models", lambda *_a, **_k: GATEWAY_CARDS)
    r = client.get("/api/agent/models", headers=auth_header(Role.SALES))
    data = r.json()["data"]
    assert [i["id"] for i in data["items"]] == ["deepseek-chat", "hunyuan-turbo", "chat-agent"]
    assert data["any_available"] and data["gateway_ok"] and data["default"] == "chat-agent"
    assert data["items"][1]["available"] is False


def test_agent_models_when_gateway_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.agent import models
    from app.common.errors import BizError

    def down(*_a: object, **_k: object) -> list:
        raise BizError(50201, "模型网关不可用")

    monkeypatch.setattr(models, "list_models", down)
    data = client.get("/api/agent/models", headers=auth_header(Role.SALES)).json()["data"]
    assert data["items"] == [] and not data["any_available"] and not data["gateway_ok"]


def test_agent_models_requires_login(client: TestClient) -> None:
    r = client.get("/api/agent/models")
    assert r.status_code == 401 and r.json()["code"] == 40101
