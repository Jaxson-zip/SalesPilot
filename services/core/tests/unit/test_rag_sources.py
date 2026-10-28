"""回复必带出处（架构设计 §5.4）：制度检索命中时推送 sources artifact，并保存到会话历史。

回归：之前 core 从不推送 sources，前端的「参考来源」从来没有显示过。
"""

from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.tools import ToolContext
from app.rag import retriever
from app.rag.retriever import PolicySearchResult, Source, source_refs, source_title
from tests.unit.test_agent import make_deps, run_chat


def _src(doc: str, section: str | None, page: int | None = None, score: float = 0.8) -> Source:
    return Source(content="x", doc_name=doc, section=section, score=score, page=page)


def test_source_title() -> None:
    assert (
        source_title(_src("费用报销管理制度", "4 客户招待 > 4.2 招待标准"))
        == "费用报销管理制度 · 4.2 招待标准"
    )
    assert source_title(_src("合同审批与回款流程", "第二章 审批权限 > 2.2 合同审批", 1)) == (
        "合同审批与回款流程 · 2.2 合同审批 · 第 1 页"
    )
    assert source_title(_src("说明", None)) == "说明"


def test_source_refs_dedupe_and_limit() -> None:
    result = PolicySearchResult(
        found=True,
        sources=[
            _src("A", "1"),
            _src("A", "1"),
            _src("B", "2"),
            _src("C", None),
            _src("D", None),
            _src("E", None),
        ],
    )
    assert [r["title"] for r in source_refs(result)] == ["A · 1", "B · 2", "C", "D"]


def test_policy_answer_emits_sources_artifact(
    tool_ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    hit = PolicySearchResult(
        found=True, sources=[_src("费用报销管理制度", "4 客户招待 > 4.2 招待标准")]
    )
    monkeypatch.setattr(retriever, "search", lambda *_a, **_k: hit)
    saver = InMemorySaver()
    deps = make_deps(tool_ctx)
    events = run_chat(deps, saver, "客户招待的报销标准是多少")

    arts = [e["data"] for e in events if e["event"] == "artifact"]
    assert arts == [{"type": "sources", "data": [{"title": "费用报销管理制度 · 4.2 招待标准"}]}]
    state: dict[str, Any] = saver.get({"configurable": {"thread_id": deps.ctx.thread_id}})[
        "channel_values"
    ]  # type: ignore[index]
    last = state["messages"][-1]
    assert {
        "type": "sources",
        "data": [{"title": "费用报销管理制度 · 4.2 招待标准"}],
    } in last.additional_kwargs["artifacts"]


def test_no_hit_no_sources(tool_ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        retriever, "search", lambda *_a, **_k: PolicySearchResult(found=False, sources=[])
    )
    events = run_chat(make_deps(tool_ctx), InMemorySaver(), "年假的报销标准是什么")
    assert not [e for e in events if e["event"] == "artifact"]


def test_search_policy_falls_back_to_rules_when_kb_unavailable(
    tool_ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """回归：没配 Embedding 时 search_policy 把「502 网关错误」交给模型，回复里出现技术报错。"""
    from app.agent.tools.policy_tools import SearchPolicyArgs, search_policy
    from app.common.errors import BizError, ErrorCode

    def unavailable(*_a: Any, **_k: Any) -> PolicySearchResult:
        raise BizError(ErrorCode.UPSTREAM, "模型网关上游错误：502")

    monkeypatch.setattr(retriever, "search", unavailable)
    result = search_policy(tool_ctx, SearchPolicyArgs(query="请客户吃饭每人能报多少"))
    assert result.ok and result.data["kb_available"] is False and result.data["found"] is False
    rules = "\n".join(line for lines in result.data["rules"].values() for line in lines)
    assert "¥150" in rules  # 招待人均标准来自 rules.yaml
    assert "502" not in result.summary
