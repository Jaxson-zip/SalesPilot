"""function calling 全链路（真实 service + 测试库，模型用剧本代替）。

覆盖场景 3 的要求：自然语言 → 意图识别 → 模型选工具并传参 → 写操作确认 → 结果回传模型 → 汇总回复。
"""

import json
import uuid
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from app.agent import service
from app.agent.deps import AgentDeps
from app.agent.sse import iter_graph_events
from app.agent.tools import ToolContext
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Expense, Opportunity
from app.crm.services.demo import DEMO_USERS
from seed.data import C_MINGLI
from tests.api.conftest import Tracker
from tests.api.test_opportunities_api import new_opp
from tests.scripted_llm import ScriptedModel, call

ROUTE_CRM = call("IntentDecision", {"intent": "crm_action"}, "route")


def _deps(role: Role, llm: ScriptedModel, thread: str) -> AgentDeps:
    ctx = ToolContext(user=DEMO_USERS[role], session=session_scope, thread_id=thread)
    return AgentDeps(ctx=ctx, resolve_pack=lambda _o: "llm_deploy", llm=llm)


def _chat(deps: AgentDeps, saver: InMemorySaver, text: str) -> list[dict[str, Any]]:
    run = service.prepare_chat(deps, text, None, checkpointer=saver)
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


def _resume(deps: AgentDeps, saver: InMemorySaver, decision: str) -> list[dict[str, Any]]:
    run = service.prepare_resume(deps, decision, saver)
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


def _of(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [e["data"] for e in events if e["event"] == name]


def _stage(opp_id: str) -> str:
    with session_scope() as db:
        opp = db.get(Opportunity, uuid.UUID(opp_id))
        assert opp is not None
        return opp.stage


def _stage_script(opp_id: str, final: str) -> list[AIMessage]:
    return [
        ROUTE_CRM,
        call("search_customer", {"keyword": "明理"}, "c1"),
        call("get_customer_context", {"customer_id": str(C_MINGLI)}, "c2"),
        call(
            "update_opportunity_stage",
            {"opportunity_id": opp_id, "stage": "negotiation", "idempotency_key": "model-made"},
            "c3",
        ),
        AIMessage(content=final),
    ]


def test_stage_change_waits_for_confirm_then_runs(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    llm = ScriptedModel(script=_stage_script(opp["id"], "已把商机推进到「商务谈判」。"))
    deps, saver = _deps(Role.SALES, llm, f"t-{uuid.uuid4().hex[:6]}"), InMemorySaver()

    events = _chat(deps, saver, "把明理律所那个测试商机推进到商务谈判")
    # 只读工具已执行，写工具停在确认卡片上，数据库没有变化
    started = [d["name"] for d in _of(events, "tool.start")]
    assert started == ["search_customer", "get_customer_context"]
    (pending,) = _of(events, "interrupt")
    assert pending["action"] == "update_opportunity_stage"
    assert pending["preview"] == {"opportunity_name": opp["name"], "stage": "商务谈判"}
    assert _stage(opp["id"]) == "lead"
    # 模型拿到的工具结果是结构化 JSON，并且带着 get_customer_context 查到的商机 id
    tool_msgs = [m for m in llm.seen[-1] if isinstance(m, ToolMessage)]
    context = json.loads(tool_msgs[-1].content)  # type: ignore[arg-type]
    assert any(o["id"] == opp["id"] for o in context["data"]["opportunities"])

    events = _resume(deps, saver, "approve")
    assert _stage(opp["id"]) == "negotiation"
    assert [d["name"] for d in _of(events, "tool.start")] == ["update_opportunity_stage"]
    assert len(_of(events, "tool.end")) == 1
    text = "".join(d["text"] for d in _of(events, "message.delta"))
    assert text == "已把商机推进到「商务谈判」。"
    last = llm.seen[-1][-1]
    assert isinstance(last, ToolMessage) and json.loads(last.content)["ok"]  # type: ignore[arg-type]


def test_reject_does_not_write_and_model_is_told(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    llm = ScriptedModel(script=_stage_script(opp["id"], "好的，已取消，商机阶段没有变化。"))
    deps, saver = _deps(Role.SALES, llm, f"t-{uuid.uuid4().hex[:6]}"), InMemorySaver()
    _chat(deps, saver, "把明理律所那个测试商机推进到商务谈判")

    events = _resume(deps, saver, "reject")
    assert _stage(opp["id"]) == "lead"
    assert not _of(events, "tool.start")
    last = llm.seen[-1][-1]
    assert isinstance(last, ToolMessage) and "取消" in str(last.content)


def test_expense_via_chat_uses_system_idempotency_key(tracker: Tracker) -> None:
    today = date.today().isoformat()
    args = {
        "type": "entertainment",
        "amount": 86_000,
        "occurred_on": today,
        "customer_id": str(C_MINGLI),
        "contact_names": ["王律师"],
        "headcount": 4,
        "reason": f"function calling 测试晚餐 {uuid.uuid4().hex[:6]}",
    }
    llm = ScriptedModel(
        script=[ROUTE_CRM, call("submit_expense", args, "e1"), AIMessage(content="已提交。")]
    )
    deps, saver = _deps(Role.SALES, llm, f"t-{uuid.uuid4().hex[:6]}"), InMemorySaver()
    (pending,) = _of(_chat(deps, saver, "昨晚请明理王律师吃饭 860，4 个人，帮我报销"), "interrupt")
    assert pending["preview"]["customer_name"] == "深圳明理律师事务所"
    assert pending["preview"]["amount"] == 86_000 and pending["preview"]["contacts"] == "王律师"

    _resume(deps, saver, "approve")
    with session_scope() as db:
        exp = db.scalars(select(Expense).where(Expense.reason == args["reason"])).one()
        tracker.expenses.append(exp.id)
        assert exp.idempotency_key == f"agent:{deps.ctx.thread_id}:e1"
        assert exp.headcount == 4


def test_admin_cannot_call_write_tools(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    llm = ScriptedModel(
        script=[
            ROUTE_CRM,
            call("update_opportunity_stage", {"opportunity_id": opp["id"], "stage": "won"}, "a1"),
            AIMessage(content="管理员只能查看业务数据。"),
        ]
    )
    events = _chat(_deps(Role.ADMIN, llm, "t-admin"), InMemorySaver(), "把这个商机改成赢单")
    assert not _of(events, "interrupt") and _stage(opp["id"]) == "lead"
    assert "update_opportunity_stage" not in llm.bound[0]  # 根本没把写工具交给模型
    refused = llm.seen[-1][-1]
    assert isinstance(refused, ToolMessage) and "不能使用" in str(refused.content)
