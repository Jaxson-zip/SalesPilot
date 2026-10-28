"""AI 用量：调用归属到人和功能、流式 / 非流式用量解析、统计接口的范围与权限、费用估算。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from sqlalchemy import delete

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import AiUsage
from app.crm.services.demo import DEMO_USERS
from app.llm import usage
from app.llm.client import get_chat_model
from app.rules import load_rules
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H

SALES = DEMO_USERS[Role.SALES]
RID = f"req_usage_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def clean() -> Iterator[None]:
    yield
    with session_scope() as db:
        db.execute(delete(AiUsage).where(AiUsage.request_id.like("req_usage_%")))


def _bind_sales(path: str) -> object:
    from app.common.auth import issue_token

    return usage.bind(path, f"Bearer {issue_token(SALES)}")


def test_feature_mapping() -> None:
    assert usage.feature_for("/api/agent/chat") == "AI 工作台"
    assert usage.feature_for("/api/agent/materials") == "材料识别"
    assert usage.feature_for("/api/opportunities/x/meddic/assess") == "赢单评估"
    assert usage.feature_for("/api/reports/daily/draft") == "日报草稿"
    assert usage.feature_for("/api/customers") == "其他"


def test_non_streaming_usage_attributed() -> None:
    token = _bind_sales("/api/reports/daily/draft")
    try:
        result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="ok"))]],
            llm_output={
                "token_usage": {"prompt_tokens": 1200, "completion_tokens": 300},
                "model_name": "deepseek-chat",
            },
        )
        usage.UsageCallback("chat-agent", RID).on_llm_end(result)
    finally:
        usage.reset(token)
    with session_scope() as db:
        row = db.query(AiUsage).filter(AiUsage.request_id == RID).one()
        assert (row.user_id, row.team_id) == (SALES.id, SALES.team_id)
        assert (row.feature, row.model) == ("日报草稿", "deepseek-chat")
        assert (row.prompt_tokens, row.completion_tokens) == (1200, 300)


def test_streaming_usage_from_message_metadata() -> None:
    rid = f"req_usage_{uuid.uuid4().hex[:8]}"
    msg = AIMessage(
        content="hi",
        usage_metadata={"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
        response_metadata={"model_name": "qwen-plus"},
    )
    usage.record("chat-agent", LLMResult(generations=[[ChatGeneration(message=msg)]]), rid)
    with session_scope() as db:
        row = db.query(AiUsage).filter(AiUsage.request_id == rid).one()
        assert row.feature == "系统" and row.user_id is None and row.model == "qwen-plus"


def test_empty_usage_not_recorded() -> None:
    rid = f"req_usage_{uuid.uuid4().hex[:8]}"
    usage.record("x", LLMResult(generations=[[ChatGeneration(message=AIMessage("a"))]]), rid)
    with session_scope() as db:
        assert db.query(AiUsage).filter(AiUsage.request_id == rid).count() == 0


def test_chat_model_has_usage_callback() -> None:
    llm = get_chat_model(streaming=False, request_id="r1")
    assert any(isinstance(cb, usage.UsageCallback) for cb in llm.callbacks or [])


def test_stats_scope_cost_and_permissions(client: TestClient) -> None:
    token = _bind_sales("/api/agent/chat")
    try:
        result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="ok"))]],
            llm_output={"token_usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0}},
        )
        usage.UsageCallback("chat-agent", RID).on_llm_end(result)
    finally:
        usage.reset(token)
    data = client.get("/api/ai-usage", params={"period": "7d"}, headers=ADMIN_H).json()["data"]
    assert data["scope"] == "company" and len(data["by_day"]) == 7
    me = next(r for r in data["by_user"] if r["key"] == str(SALES.id))
    price = load_rules().ai_usage.input_price_per_million
    assert me["prompt_tokens"] >= 1_000_000 and me["cost"] >= round(price * 100)
    assert any(r["label"] == "AI 工作台" for r in data["by_feature"])
    assert data["by_day"][-1]["calls"] >= 1

    team = client.get("/api/ai-usage", headers=MANAGER_H).json()["data"]
    assert team["scope"] == "team" and len(team["by_day"]) == 30
    assert client.get("/api/ai-usage", headers=SALES_H).json()["code"] == 40301
    assert (
        client.get("/api/ai-usage", params={"period": "x"}, headers=ADMIN_H).json()["code"] == 40001
    )
