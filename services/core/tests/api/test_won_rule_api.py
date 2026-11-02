"""赢单必须按报价成交：接口拒绝没指定报价的赢单；对话里不再先弹确认卡再报错。"""

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.common.auth import Role
from tests.api.conftest import SALES_H, Tracker
from tests.api.test_agent_function_calling import _chat, _deps, _of, _stage
from tests.api.test_opportunities_api import new_opp
from tests.api.test_quotes_contracts_api import approved_quote
from tests.scripted_llm import ScriptedModel, call


def test_won_without_quote_rejected_with_hint(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}/stage"
    none = client.patch(url, json={"stage": "won"}, headers=SALES_H).json()
    assert none["code"] == 42201 and none["data"] == {"rule": "won_needs_quote", "quotes": []}
    assert "请先出报价并审批通过" in none["message"]

    qid = approved_quote(client, tracker, opp["id"])
    listed = client.patch(url, json={"stage": "won"}, headers=SALES_H).json()
    assert listed["code"] == 42201 and [q["id"] for q in listed["data"]["quotes"]] == [qid]
    assert "请选择按报价" in listed["message"]
    won = client.patch(url, json={"stage": "won", "quote_id": qid}, headers=SALES_H).json()
    assert won["code"] == 0 and won["data"]["stage"] == "won"


def test_agent_won_without_quote_skips_confirm_card(client: TestClient, tracker: Tracker) -> None:
    """回归：原来先弹「确认赢单」卡片，用户点了确认才报错。"""
    opp = new_opp(client, tracker)
    llm = ScriptedModel(
        script=[
            call("update_opportunity_stage", {"opportunity_id": opp["id"], "stage": "won"}, "w1"),
            AIMessage(content="这个商机还没有已审批的报价，先出报价吧。"),
        ]
    )
    events = _chat(_deps(Role.SALES, llm, "t-won-precheck"), InMemorySaver(), "这单赢了")
    assert not _of(events, "interrupt") and _stage(opp["id"]) == "lead"
    refused = llm.seen[-1][-1]
    assert isinstance(refused, ToolMessage) and "赢单需要按报价成交" in str(refused.content)
