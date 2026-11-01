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


def test_solution_flow_uses_chosen_pack() -> None:
    """回归：选了软件外包，出方案节点又按团队默认（大模型部署）取行业包，追问并发和模型。"""
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=THREAD)
    deps = AgentDeps(ctx=ctx, resolve_pack=lambda _o: "llm_deploy", llm=None)
    msg = "帮我出方案：做一个蛋糕预订微信小程序，在线支付，会员积分"
    run = service.prepare_chat(
        deps, msg, None, checkpointer=InMemorySaver(), pack="software_outsourcing"
    )
    events = list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))
    card = next(e["data"] for e in events if e["event"] == "artifact")
    assert card["type"] == "requirement" and card["data"]["pack_id"] == "software_outsourcing"


def _solution(pack: str | None) -> tuple[dict, str, dict]:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=THREAD)
    # 星河设计工作室有唯一进行中的商机「IT 设备换新」，产品线是企业办公 IT
    deps = AgentDeps(ctx=ctx, resolve_pack=lambda o: "it_office" if o else "llm_deploy", llm=None)
    msg = "给星河设计工作室做一个微信预约小程序，服务预约、订单查询、管理后台，预算10万元"
    run = service.prepare_chat(deps, msg, None, checkpointer=InMemorySaver(), pack=pack)
    events = list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))
    text = "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
    return run.graph.get_state(run.config).values, text, events


def test_chosen_pack_wins_over_auto_linked_opportunity() -> None:
    """回归：手选软件外包，提到的客户恰好有一个办公 IT 商机，被自动关联后追问「配几台电脑」，
    纠正后仍重复，重新打开会话也显示企业办公 IT。现在按手选行业包、作为新项目，不关联那个商机。"""
    state, text, events = _solution("software_outsourcing")
    assert state["pack_id"] == "software_outsourcing"
    assert not state.get("opportunity_id") and state["customer_name"] == "星河设计工作室"
    assert "「IT 设备换新」" in text and "新项目" in text
    card = next(e["data"] for e in events if e["event"] == "artifact")
    assert card["data"]["pack_id"] == "software_outsourcing"
    assert "电脑" not in text


def test_auto_linked_opportunity_used_without_choice() -> None:
    state, text, _ = _solution(None)
    assert state["pack_id"] == "it_office" and state.get("opportunity_id")
    assert "新项目" not in text
