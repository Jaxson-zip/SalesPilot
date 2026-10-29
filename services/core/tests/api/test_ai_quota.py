"""每人每日 AI tokens 上限：超过后新的对话、识别、日报草稿返回 42901，确认操作不受影响。"""

import pytest
from fastapi.testclient import TestClient

from app.common.auth import Role
from app.crm.services import usage_service
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import SALES_H


def test_daily_quota_blocks_new_ai_calls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(usage_service, "tokens_today", lambda *_a: 2_000_000)
    body = {"thread_id": "t-quota", "message": "给明理律所出方案"}
    r = client.post("/api/agent/chat", json=body, headers=SALES_H)
    assert r.status_code == 429 and r.json()["code"] == 42901
    assert "已达上限" in r.json()["message"]
    files = {"file": ("a.png", b"\x89PNG", "image/png")}
    assert client.post("/api/agent/samples", files=files, headers=SALES_H).json()["code"] == 42901
    draft = client.post("/api/reports/daily/draft", json={}, headers=SALES_H).json()
    assert draft["code"] == 42901


def test_daily_quota_under_limit_and_zero_means_unlimited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = DEMO_USERS[Role.SALES]
    monkeypatch.setattr(usage_service, "tokens_today", lambda *_a: 1_999_999)
    usage_service.ensure_daily_quota(user)  # 不到上限：不抛错
    rules = usage_service.load_rules()
    off = rules.model_copy(
        update={"ai_usage": rules.ai_usage.model_copy(update={"user_daily_tokens": 0})}
    )
    monkeypatch.setattr(usage_service, "tokens_today", lambda *_a: 10**9)
    monkeypatch.setattr(usage_service, "load_rules", lambda: off)
    usage_service.ensure_daily_quota(user)  # 0 表示不限


def test_tokens_today_query_runs() -> None:
    from app.common.db import session_scope

    with session_scope() as db:
        assert usage_service.tokens_today(db, DEMO_USERS[Role.SALES].id) >= 0
