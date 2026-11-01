"""没关联商机时在输入框选行业包：本轮和之后几轮都按选的查资料、出方案；关联了商机以商机产品线为准。"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import delete

from app.agent import service
from app.agent.deps import AgentDeps
from app.agent.history import build_messages
from app.agent.sse import iter_graph_events
from app.agent.tools import ToolContext
from app.common.auth import Role
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.crm.models import AgentThread
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import SALES_H
from tests.scripted_llm import ScriptedModel

THREAD = f"t-pack-{uuid.uuid4().hex[:6]}"


@pytest.fixture(autouse=True)
def clean_thread() -> Iterator[None]:
    yield
    with session_scope() as db:
        db.execute(delete(AgentThread).where(AgentThread.thread_id == THREAD))


def _deps() -> AgentDeps:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=THREAD)
    llm = ScriptedModel(script=[AIMessage(content="好的")] * 4)
    # 团队默认行业包是大模型部署
    return AgentDeps(ctx=ctx, resolve_pack=lambda _o: "llm_deploy", llm=llm)


def _turn(saver: InMemorySaver, text: str, **kw: object) -> dict:
    run = service.prepare_chat(_deps(), text, None, checkpointer=saver, **kw)  # type: ignore[arg-type]
    list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))
    return run.payload


def test_chosen_pack_used_and_kept_across_turns() -> None:
    """回归：没从商机进入时行业包锁定为团队默认，说外包需求 AI 却按大模型部署问 GPU。"""
    saver = InMemorySaver()
    assert _turn(saver, "做个蛋糕预订小程序", pack="software_outsourcing")["pack_id"] == (
        "software_outsourcing"
    )
    assert _turn(saver, "预算 3 万")["pack_id"] == "software_outsourcing"  # 第二轮不传也沿用
    run = service.prepare_chat(_deps(), "再看看", None, checkpointer=saver)
    assert run.base.pack_choice == "software_outsourcing"  # 打开历史会话时恢复选择
    assert build_messages(THREAD, run.graph.get_state(run.config)).pack_choice == (
        "software_outsourcing"
    )


def test_without_choice_uses_team_default() -> None:
    assert _turn(InMemorySaver(), "你好")["pack_id"] == "llm_deploy"


def test_opportunity_wins_over_choice() -> None:
    run = service.prepare_chat(
        _deps(), "出方案", uuid.uuid4(), checkpointer=InMemorySaver(), pack="software_outsourcing"
    )
    assert run.payload["pack_id"] == "llm_deploy"


def test_unknown_pack_rejected(client: TestClient) -> None:
    with pytest.raises(BizError) as err:
        service.prepare_chat(_deps(), "你好", None, checkpointer=InMemorySaver(), pack="nope")
    assert err.value.code == ErrorCode.VALIDATION
    body = {"thread_id": THREAD, "message": "你好", "pack": "nope"}
    r = client.post("/api/agent/chat", json=body, headers=SALES_H)
    assert r.json()["code"] == ErrorCode.VALIDATION
