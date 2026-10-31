"""AI 写操作统一「准备 → 确认 → 执行」、执行状态驱动回复、行业包跟随会话、客户资料字段齐全。

模型用剧本代替（tests/scripted_llm.py），service 和数据库是真实的。
"""

import uuid
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from app.agent import service
from app.agent.deps import AgentDeps
from app.agent.nodes.common import call_tool
from app.agent.sse import iter_graph_events
from app.agent.tools import TOOLS, ToolContext
from app.agent.tools.policy_tools import SearchPolicyArgs, search_policy
from app.common.auth import Role
from app.common.db import session_scope
from app.common.errors import BizError
from app.crm.models import Followup
from app.crm.services.demo import DEMO_USERS
from app.rag import retriever
from app.rag.retriever import PolicySearchResult
from seed.data import C_MINGLI
from tests.api.conftest import Tracker
from tests.scripted_llm import ScriptedModel, call

ASKS_AGAIN = "请确认卡片，确认后即写入系统。"


def _deps(llm: ScriptedModel | None, pack: str = "llm_deploy") -> AgentDeps:
    thread = f"t-{uuid.uuid4().hex[:8]}"
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope, thread_id=thread)
    return AgentDeps(ctx=ctx, resolve_pack=lambda _o: pack, llm=llm)


def _run(run: service.PreparedRun) -> list[dict[str, Any]]:
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


def _of(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [e["data"] for e in events if e["event"] == name]


def _followups(content: str) -> list[Followup]:
    with session_scope() as db:
        rows = list(db.scalars(select(Followup).where(Followup.content == content)))
        for r in rows:
            db.expunge(r)
        return rows


def _followup_script(content: str) -> list[AIMessage]:
    args = {"customer_id": str(C_MINGLI), "content": content, "type": "phone"}
    # 执行之后模型还在让用户确认：回复要按执行状态改正
    return [call("add_followup", args, "f1"), AIMessage(content=ASKS_AGAIN)]


def test_followup_waits_for_confirm_and_reply_follows_status(tracker: Tracker) -> None:
    content = f"电话跟进测试 {uuid.uuid4().hex[:6]}"
    deps, saver = _deps(ScriptedModel(script=_followup_script(content))), InMemorySaver()
    events = _run(
        service.prepare_chat(deps, "给明理记一条电话跟进，先给确认卡片", None, checkpointer=saver)
    )
    (pending,) = _of(events, "interrupt")
    assert pending["action"] == "add_followup"
    assert pending["preview"] == {
        "customer_name": "深圳明理律师事务所",
        "followup_type": "电话",
        "followup": content,
    }
    assert _followups(content) == []  # 确认之前没有写入

    events = _run(service.prepare_resume(deps, "approve", saver))
    rows = _followups(content)
    tracker.followups += [r.id for r in rows]
    assert len(rows) == 1
    (res,) = [a["data"] for a in _of(events, "artifact") if a["type"] == "action_result"]
    assert res["status"] == "done" and res["href"] == f"/customers/{C_MINGLI}"
    # 模型说「请确认卡片」：服务端按执行结果改正，保存的回复也是改正后的
    (fixed,) = _of(events, "message.replace")
    assert fixed["text"] == "已完成：已记录跟进。"
    graph = service.build_graph(deps, saver)
    saved = graph.get_state(service._config(deps.ctx.thread_id)).values["messages"][-1]
    assert saved.content == "已完成：已记录跟进。"
    assert "确认" not in saved.content
    assert {"type": "action_result", "data": res} in saved.additional_kwargs["artifacts"]

    # 重复确认：没有待确认的操作，不会再写一条
    with pytest.raises(BizError, match="没有待确认的操作"):
        service.prepare_resume(deps, "approve", saver)
    assert len(_followups(content)) == 1


def test_cancel_writes_nothing(tracker: Tracker) -> None:
    content = f"取消的跟进 {uuid.uuid4().hex[:6]}"
    script = [*_followup_script(content)[:2], AIMessage(content="好的，已取消。")]
    deps, saver = _deps(ScriptedModel(script=script)), InMemorySaver()
    _run(service.prepare_chat(deps, "给明理记一条电话跟进", None, checkpointer=saver))
    events = _run(service.prepare_resume(deps, "reject", saver))
    assert _followups(content) == []
    assert not _of(events, "tool.start")
    (res,) = [a["data"] for a in _of(events, "artifact") if a["type"] == "action_result"]
    assert res["status"] == "cancelled" and res["href"] is None


def test_rule_fallback_never_writes() -> None:
    """没有模型时按关键词兜底：只查不写，「记录跟进」也不会直接写库。"""
    text = f"给深圳明理律师事务所记录电话跟进 {uuid.uuid4().hex[:6]}"
    events = _run(service.prepare_chat(_deps(None), text, None, checkpointer=InMemorySaver()))
    assert "add_followup" not in [d["name"] for d in _of(events, "tool.start")]
    assert _followups(text) == []


def test_write_tool_refuses_without_confirmation() -> None:
    deps = _deps(None)
    args = {"customer_id": str(C_MINGLI), "content": "绕过确认"}
    result = call_tool(deps, "add_followup", args)
    assert not result.ok and "必须先让用户确认" in result.summary
    assert all(t.needs_confirm for t in TOOLS.values() if t.write)


# ---------- 行业包跟随会话 ----------


def test_context_pack_reaches_search_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """团队默认产品线是软件外包：检索参数跟着走，而不是系统默认的 llm_deploy。"""
    seen: list[list[str]] = []

    def fake_search(_db: Any, _q: str, scopes: list[str], **_: Any) -> PolicySearchResult:
        seen.append(scopes)
        return PolicySearchResult(found=False, sources=[])

    monkeypatch.setattr(retriever, "search", fake_search)
    script = [
        call("search_policy", {"query": "云服务和短信费用包含在报价里吗"}, "p1"),
        AIMessage(content="这次检索范围里没有命中。"),
    ]
    deps = _deps(ScriptedModel(script=script), pack="software_outsourcing")
    events = _run(
        service.prepare_chat(deps, "云服务费用含在报价里吗", None, checkpointer=InMemorySaver())
    )
    assert seen == [["company", "pack:software_outsourcing"]]
    (end,) = _of(events, "tool.end")
    # 没命中只说明这个范围：不能说成平台没有文档
    assert "「软件外包」" in end["summary"] and "只代表这次检索范围内没命中" in end["summary"]


def test_user_named_pack_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(
        retriever,
        "search",
        lambda _db, _q, scopes, **_: (
            seen.append(scopes) or PolicySearchResult(found=False, sources=[])
        ),
    )
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope)
    search_policy(
        ctx, SearchPolicyArgs(query="x", pack_id="llm_deploy", pack="software_outsourcing")
    )
    search_policy(ctx, SearchPolicyArgs(query="x", pack_id="llm_deploy", pack="no_such_pack"))
    assert seen == [["company", "pack:software_outsourcing"], ["company", "pack:llm_deploy"]]


# ---------- 客户资料字段 ----------


def test_customer_context_has_level() -> None:
    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=session_scope)
    result = call_tool(_deps(None), "search_customer", {"keyword": "明理"})
    assert result.ok and "level" in result.data[0]
    from app.agent.tools.context_tools import CustomerContextArgs, get_customer_context

    out = get_customer_context(ctx, CustomerContextArgs(customer_id=C_MINGLI))
    with session_scope() as db:
        from app.crm.models import Customer

        level = db.scalar(select(Customer.level).where(Customer.id == C_MINGLI))
    assert out.data["customer"]["level"] == level


def test_only_card_confirm_phrases_count_as_contradiction() -> None:
    from app.agent.action_result import contradicts

    done = {"status": "done"}
    assert contradicts("请确认卡片，确认后即写入系统。", done)
    assert contradicts("确认后才会写入", done)
    # 正常的下一步建议不能被当成「还在让用户确认」而整句替换
    assert not contradicts("已记录跟进。请确认下周是否需要拜访", done)
    assert not contradicts("请确认卡片", {"status": "cancelled"})


def test_done_links_open_the_written_record() -> None:
    """确认执行后「查看记录」直接打开刚写的那条，而不是只到列表页。"""
    from app.agent.action_result import action_result
    from app.agent.tools import ToolResult

    def href(name: str, data: dict[str, Any]) -> str | None:
        return action_result(name, "approve", ToolResult(ok=True, summary="ok", data=data))["href"]

    assert href("submit_expense", {"id": "e1"}) == "/expenses?id=e1"
    assert href("update_opportunity_stage", {"id": "o1"}) == "/pipeline?opp=o1"
    assert href("decide_approval", {"id": "a1"}) == "/approvals?id=a1"
    task = {"id": "t1", "subject_type": "opportunity", "subject_id": "o1"}
    assert href("create_task", task) == "/pipeline?opp=o1&task=t1"
    task = {"id": "t2", "subject_type": "customer", "subject_id": "c1"}
    assert href("create_task", task) == "/customers/c1?task=t2"
    # 拿不到 id 时退回列表页
    assert href("submit_expense", {}) == "/expenses"
