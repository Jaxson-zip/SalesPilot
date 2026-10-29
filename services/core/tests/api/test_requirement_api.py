"""商机需求清单：出方案时 AI 拆出的需求保存在商机上，确认后记动态，下次出方案接着用。"""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import service
from app.agent.deps import AgentDeps
from app.agent.graph import build_graph
from app.agent.history import build_messages
from app.agent.sse import iter_graph_events
from app.agent.tools import ToolContext
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import SALES2_H, SALES_H, Tracker

MSG = "出个方案：门店预约小程序，要会员登录和在线预约，还要管理后台"


def _opp(client: TestClient, tracker: Tracker) -> str:
    body = {"name": f"需求清单测试-{uuid.uuid4().hex[:6]}", "level": "B"}
    cid = client.post("/api/customers", json=body, headers=SALES_H).json()["data"]["id"]
    tracker.customers.append(uuid.UUID(cid))
    opp = client.post(
        "/api/opportunities",
        json={"customer_id": cid, "name": "预约小程序", "amount": 15_000_000},
        headers=SALES_H,
    ).json()["data"]
    return str(opp["id"])


def _run(
    thread: str, opp_id: str | None, message: str, requirement: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=thread)
    deps = AgentDeps(ctx=ctx, resolve_pack=lambda _o: "software_outsourcing", llm=None)
    run = service.prepare_chat(
        deps,
        message,
        uuid.UUID(opp_id) if opp_id else None,
        checkpointer=SAVER,
        requirement=requirement,
    )
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


SAVER = InMemorySaver()


def test_requirement_saved_confirmed_and_reused(client: TestClient, tracker: Tracker) -> None:
    opp_id = _opp(client, tracker)
    url = f"/api/opportunities/{opp_id}/requirement"
    assert client.get(url, headers=SALES_H).json()["data"] is None

    thread = f"req-{uuid.uuid4().hex[:8]}"
    events = _run(thread, opp_id, MSG)
    card = next(e for e in events if e["event"] == "artifact")["data"]["data"]
    saved = client.get(url, headers=SALES_H).json()["data"]
    assert saved["pack"] == "software_outsourcing" and not saved["confirmed"]
    assert saved["price_low"] == card["price_low"] and saved["questions"]
    assert client.get(url, headers=SALES2_H).json()["code"] == 40401  # 别人的商机看不到

    events = _run(thread, opp_id, "需求已确认", card["requirement"])
    assert [e["event"] for e in events][-2:] == ["interrupt", "done"]
    saved = client.get(url, headers=SALES_H).json()["data"]
    assert saved["confirmed"] and saved["price_low"] == card["price_low"]  # 确认时沿用区间
    acts = client.get(f"/api/opportunities/{opp_id}", headers=SALES_H).json()["data"]["activities"]
    assert any(a["action"] == "requirement_confirmed" for a in acts)

    # 换一个新会话从商机进入：直接按已确认的需求出方案
    events = _run(f"req-{uuid.uuid4().hex[:8]}", opp_id, "按之前的需求出方案")
    arts = [e["data"]["type"] for e in events if e["event"] == "artifact"]
    assert "requirement" not in arts and "solution_tiers" in arts


def test_reopened_thread_keeps_opportunity(client: TestClient, tracker: Tracker) -> None:
    """从历史记录重新打开的会话不再带 opportunity_id：仍关联原商机，确认的需求存回商机。"""
    opp_id = _opp(client, tracker)
    thread = f"req-{uuid.uuid4().hex[:8]}"
    card = next(e for e in _run(thread, opp_id, MSG) if e["event"] == "artifact")["data"]["data"]
    assert card["opportunity_id"] == opp_id

    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=thread)
    deps = AgentDeps(ctx=ctx, resolve_pack=lambda _o: "software_outsourcing", llm=None)
    graph_values = build_graph(deps, SAVER).get_state({"configurable": {"thread_id": thread}})
    assert build_messages(thread, graph_values).opportunity_id == opp_id

    _run(thread, None, "需求已确认", card["requirement"])
    saved = client.get(f"/api/opportunities/{opp_id}/requirement", headers=SALES_H).json()
    assert saved["data"]["confirmed"]
