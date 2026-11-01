"""学习问答模式：只给知识类只读工具、提示词要求标出处、模式随会话保留、业务概览不含成本。"""

import json
import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import delete, select

from app.agent import service
from app.agent.deps import AgentDeps
from app.agent.sse import iter_graph_events
from app.agent.state import Mode
from app.agent.tools import LEARN_TOOL_NAMES, TOOLS, ToolContext, tools_for
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import AgentThread
from app.crm.services import settings_service
from app.crm.services.demo import DEMO_USERS
from app.packs.registry import list_packs
from app.rag import retriever
from app.rag.retriever import PolicySearchResult
from tests.api.conftest import SALES_H
from tests.scripted_llm import ScriptedModel, call

THREAD = f"t-learn-{uuid.uuid4().hex[:6]}"


@pytest.fixture(autouse=True)
def clean_thread() -> Iterator[None]:
    yield
    with session_scope() as db:
        db.execute(delete(AgentThread).where(AgentThread.thread_id == THREAD))


def _deps(llm: ScriptedModel, role: Role = Role.SALES) -> AgentDeps:
    ctx = ToolContext(user=DEMO_USERS[role], session=session_scope, thread_id=THREAD)
    return AgentDeps(ctx=ctx, resolve_pack=lambda _o: "llm_deploy", llm=llm)


def _chat(deps: AgentDeps, saver: InMemorySaver, text: str, mode: Mode) -> list[dict[str, Any]]:
    run = service.prepare_chat(deps, text, None, checkpointer=saver, mode=mode)
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


def _of(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [e["data"] for e in events if e["event"] == name]


def test_learn_tools_are_read_only_and_same_for_every_role() -> None:
    for role in Role:
        tools = tools_for(role, "learn")
        assert [t.name for t in tools] == list(LEARN_TOOL_NAMES)
        assert all(not t.write and not t.needs_confirm for t in tools)


def test_learn_mode_uses_knowledge_tools_only() -> None:
    llm = ScriptedModel(
        script=[
            call("get_business_overview", {"topic": "products"}, "c1"),
            # 模型想在学习模式里写数据：工具不可见，执行时也会被拒绝
            call("submit_expense", {"amount": 100, "category": "meal"}, "c2"),
            AIMessage(
                content="公司有三条产品线（出处：系统业务规则）\n可以接着问：\n- 报价怎么审批"
            ),
        ]
    )
    deps, saver = _deps(llm), InMemorySaver()
    events = _chat(deps, saver, "公司卖什么？", "learn")

    # 不走意图识别，直接进工具循环；只绑定知识类工具
    assert llm.bound and all(set(b) == set(LEARN_TOOL_NAMES) for b in llm.bound)
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage)
    assert "学习问答模式" in system.content and "出处" in system.content
    assert "示例资料" in system.content  # 行业包仍是示例资料时提醒
    assert [d["name"] for d in _of(events, "tool.start")] == ["get_business_overview"]
    assert not _of(events, "action.confirm")
    refused = json.loads(llm.seen[-1][-1].content)
    assert refused["ok"] is False and "submit_expense" in refused["summary"]

    with session_scope() as db:
        row = db.scalar(select(AgentThread).where(AgentThread.thread_id == THREAD))
        assert row is not None and row.mode == "learn"


def test_mode_is_fixed_when_thread_is_created() -> None:
    first = ScriptedModel(script=[AIMessage(content="好的")])
    saver = InMemorySaver()
    _chat(_deps(first), saver, "提成怎么算？", "learn")
    # 第二轮请求 work 也沿用会话的 learn 模式（不会切到能写数据的工具）
    second = ScriptedModel(script=[AIMessage(content="好的")])
    _chat(_deps(second), saver, "帮我报销 100 元", "work")
    assert second.bound and set(second.bound[0]) == set(LEARN_TOOL_NAMES)


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _catalog() -> list[Any]:
    return [row for pack in list_packs().values() for row in settings_service.catalog_rows(pack)]


def test_business_overview_has_catalog_rules_and_no_cost() -> None:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=THREAD)
    spec = TOOLS["get_business_overview"]
    result = spec.func(ctx, spec.args_model())
    assert result.ok
    data = result.data
    assert data["products"] and all(p["catalog"] for p in data["products"])
    assert all(p["sample_data"] is True for p in data["products"])
    assert data["pipeline"][0]["stage"] == "线索"
    assert {"commission", "quote", "expense"} <= set(data["rules"])
    # 新人看目录价，不给成本：任何层级都没有 cost 字段，也没有成本价金额
    assert not _keys(data) & {"cost", "default_cost", "unit_cost", "total_cost"}
    costs = {f"¥{row.cost / 100:,.0f}" for row in _catalog()}
    prices = {f"¥{row.price / 100:,.0f}" for row in _catalog()}
    text = json.dumps(data, ensure_ascii=False)
    # 按完整金额匹配：成本 ¥200 不能误判成目录价 ¥200,000 的前缀
    assert not any(re.search(re.escape(c) + r"(?![\d,])", text) for c in costs - prices)


def test_templates_and_packs_expose_learn_prompts_and_sample_flag(client: TestClient) -> None:
    t = client.get("/api/templates", headers=SALES_H).json()["data"]
    assert len(t["learn_prompts"]) >= 6
    assert all(p["title"] and p["prompt"] for p in t["learn_prompts"])
    packs = client.get("/api/packs", headers=SALES_H).json()["data"]
    assert packs and all(p["sample_data"] is True for p in packs)
    detail = client.get(f"/api/packs/{packs[0]['id']}", headers=SALES_H).json()["data"]
    assert detail["sample_data"] is True


def _capture_scopes(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_search(_db: Any, _query: str, scopes: list[str], **_kw: Any) -> PolicySearchResult:
        seen.append(scopes)
        return PolicySearchResult(found=False, sources=[])

    monkeypatch.setattr(retriever, "search", fake_search)
    return seen


def test_learn_mode_searches_every_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    """回归：学习问答原来只查团队默认行业包，问软件外包的问题查不到《需求变更与验收》。"""
    seen = _capture_scopes(monkeypatch)
    llm = ScriptedModel(
        script=[call("search_policy", {"query": "中途加功能怎么收费"}, "c1"), AIMessage("没找到")]
    )
    events = _chat(_deps(llm), InMemorySaver(), "客户开发到一半要加功能，怎么收费？", "learn")
    assert seen == [["company", *(f"pack:{p}" for p in list_packs())]]
    assert "全部行业资料" in _of(events, "tool.end")[0]["summary"]
    # 系统注入的字段不暴露给模型
    assert "all_packs" not in json.dumps(TOOLS["search_policy"].openai_schema())


def test_learn_mode_still_honours_named_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture_scopes(monkeypatch)
    llm = ScriptedModel(
        script=[
            call("search_policy", {"query": "源码", "pack": "software_outsourcing"}, "c1"),
            AIMessage("没找到"),
        ]
    )
    _chat(_deps(llm), InMemorySaver(), "软件外包的源码给不给客户？", "learn")
    assert seen == [["company", "pack:software_outsourcing"]]


def test_work_mode_searches_current_pack_only(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture_scopes(monkeypatch)
    spec = TOOLS["search_policy"]
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=THREAD)
    spec.func(ctx, spec.args_model(query="报销标准", pack_id="llm_deploy"))
    assert seen == [["company", "pack:llm_deploy"]]
