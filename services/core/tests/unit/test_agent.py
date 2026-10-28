"""Agent：工具包装、意图路由、状态图事件序列（假模型 + 内存 checkpointer，离线可跑）。"""

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import service
from app.agent.deps import AgentDeps
from app.agent.nodes.router import classify_intent
from app.agent.sse import iter_graph_events, to_sse
from app.agent.tools import TOOLS, ToolContext, run_tool
from app.common.auth import Role
from app.common.errors import BizError
from app.crm.services.demo import DEMO_USERS

SOLUTION_MSG = (
    "给深圳明理律所出一份私有化部署方案：Qwen3-32B，50 人并发，做合同审查，预算 40 万以内"
)


def make_deps(ctx: ToolContext, llm: Any = None, max_retries: int = 2) -> AgentDeps:
    return AgentDeps(
        ctx=ctx, resolve_pack=lambda _opp: "llm_deploy", llm=llm, max_retries=max_retries
    )


def run_chat(deps: AgentDeps, saver: InMemorySaver, message: str) -> list[dict[str, Any]]:
    run = service.prepare_chat(deps, message, None, checkpointer=saver)
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


def run_resume(deps: AgentDeps, saver: InMemorySaver, decision: str) -> list[dict[str, Any]]:
    run = service.prepare_resume(deps, decision, saver)
    return list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))


def names(events: list[dict[str, Any]]) -> list[str]:
    return [e["event"] for e in events]


class TestTools:
    def test_registry_matches_spec(self) -> None:
        expected = {
            "search_customer",
            "add_followup",
            "digest_material",
            "get_meddic",
            "get_battlecard",
            "get_company_intel",
            "update_opportunity_stage",
            "pipeline_summary",
            "parse_requirement",
            "configure_solution",
            "query_catalog",
            "generate_quote",
            "check_margin",
            "calc_commission",
            "search_policy",
            "submit_expense",
            "decide_approval",
            "create_task",
            "get_customer_context",
            "list_pending_approvals",
        }
        assert set(TOOLS) == expected
        confirm = {n for n, t in TOOLS.items() if t.needs_confirm}
        assert confirm == {
            "update_opportunity_stage",
            "generate_quote",
            "submit_expense",
            "decide_approval",
            "create_task",
            "digest_material",
        }

    def test_success_emits_start_end(self, tool_ctx: ToolContext) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        result = run_tool(
            TOOLS["query_catalog"],
            tool_ctx,
            {"pack_id": "llm_deploy", "keyword": "L20"},
            lambda e, d: events.append((e, d)),
        )
        assert result.ok and result.summary == "筛选出 3 个产品"
        assert [e for e, _ in events] == ["tool.start", "tool.end"]
        assert events[0][1]["call_id"] == events[1][1]["call_id"]

    def test_validation_error_returns_not_raises(self, tool_ctx: ToolContext) -> None:
        events: list[str] = []
        result = run_tool(
            TOOLS["check_margin"],
            tool_ctx,
            {"pack_id": "llm_deploy"},
            lambda e, d: events.append(e),
        )
        assert not result.ok and result.error and result.error["code"] == 40001
        assert events == ["tool.start", "tool.error"]

    def test_biz_error_code_passthrough(self, tool_ctx: ToolContext) -> None:
        result = run_tool(TOOLS["query_catalog"], tool_ctx, {"pack_id": "nope"}, lambda e, d: None)
        assert not result.ok and result.error and result.error["code"] == 40401

    def test_calc_commission_tool(self, tool_ctx: ToolContext) -> None:
        args = {"lines": [{"category": "software", "amount": 100_000}], "margin_rate": 0.3}
        result = run_tool(TOOLS["calc_commission"], tool_ctx, args, lambda e, d: None)
        assert result.ok and result.data["estimated"] == 8_000

    def test_openai_schema(self) -> None:
        schema = TOOLS["search_customer"].openai_schema()
        assert schema["function"]["name"] == "search_customer"
        assert "keyword" in schema["function"]["parameters"]["properties"]


@pytest.mark.parametrize(
    ("text", "pending", "intent"),
    [
        ("给他们出一个 Qwen3-32B 私有化方案", False, "solution"),
        ("帮我记一下：今天和明理律所通了电话", False, "crm_action"),
        ("50 人并发", True, "solution"),
        ("你好", False, "chitchat"),
    ],
)
def test_classify_intent(text: str, pending: bool, intent: str) -> None:
    assert classify_intent(text, pending) == intent


class TestSolutionFlow:
    def test_full_flow_with_retry_interrupt_and_resume(
        self, tool_ctx: ToolContext, fake_quotes: None
    ) -> None:
        saver, deps = InMemorySaver(), make_deps(tool_ctx)
        events = run_chat(deps, saver, SOLUTION_MSG)
        seq = names(events)
        assert seq[0] == "node.start" and seq[-2:] == ["interrupt", "done"]
        assert seq.count("node.retry") == 1 and "error" not in seq
        retry = next(e for e in events if e["event"] == "node.retry")
        assert retry["data"]["node"] == "configure" and retry["data"]["attempt"] == 1
        tiers = next(e for e in events if e["event"] == "artifact")["data"]
        assert tiers["type"] == "solution_tiers" and len(tiers["data"]) == 3
        interrupt = events[-2]["data"]
        assert interrupt["action"] == "generate_quote"
        assert interrupt["preview"]["total_price"] == 37_200_000

        resumed = run_resume(deps, saver, "approve")
        seq = names(resumed)
        assert seq[-1] == "done" and "message.delta" in seq
        assert any(e["event"] == "artifact" and e["data"]["type"] == "quote" for e in resumed)
        text = "".join(e["data"]["text"] for e in resumed if e["event"] == "message.delta")
        assert "Q-2026-001" in text and "372,000" in text

    def test_reject_does_not_write(self, tool_ctx: ToolContext, fake_quotes: None) -> None:
        saver, deps = InMemorySaver(), make_deps(tool_ctx)
        run_chat(deps, saver, SOLUTION_MSG)
        resumed = run_resume(deps, saver, "reject")
        assert not any(
            e["data"].get("name") == "generate_quote" for e in resumed if e["event"] == "tool.start"
        )
        text = "".join(e["data"]["text"] for e in resumed if e["event"] == "message.delta")
        assert "已取消" in text

    def test_missing_info_asks_user_then_continues(self, tool_ctx: ToolContext) -> None:
        saver, deps = InMemorySaver(), make_deps(tool_ctx)
        first = run_chat(deps, saver, "帮我出一个 Qwen3-32B 私有化方案")
        assert "interrupt" not in names(first)
        ask = "".join(e["data"]["text"] for e in first if e["event"] == "message.delta")
        assert "并发" in ask
        second = run_chat(deps, saver, "50 人并发")
        assert names(second)[-2:] == ["interrupt", "done"]

    def test_margin_gives_up_after_max_retries(self, tool_ctx: ToolContext) -> None:
        saver, deps = InMemorySaver(), make_deps(tool_ctx, max_retries=0)
        events = run_chat(deps, saver, SOLUTION_MSG)
        assert "interrupt" not in names(events) and "node.retry" not in names(events)
        text = "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
        assert "仍不达标" in text

    def test_resume_without_pending_interrupt(self, tool_ctx: ToolContext) -> None:
        with pytest.raises(BizError) as exc:
            service.prepare_resume(make_deps(tool_ctx), "approve", InMemorySaver())
        assert exc.value.code == 40401

    def test_other_user_cannot_resume(self, tool_ctx: ToolContext, null_session: Any) -> None:
        saver = InMemorySaver()
        run_chat(make_deps(tool_ctx), saver, SOLUTION_MSG)
        other = ToolContext(
            user=DEMO_USERS[Role.MANAGER], session=null_session, thread_id=tool_ctx.thread_id
        )
        with pytest.raises(BizError) as exc:
            service.prepare_resume(make_deps(other), "approve", saver)
        assert exc.value.code == 40401


class TestOtherIntents:
    def test_chitchat_streams_llm(self, tool_ctx: ToolContext) -> None:
        llm = GenericFakeChatModel(messages=iter([AIMessage(content="你好 我是 SalesPilot")]))
        events = run_chat(make_deps(tool_ctx, llm=llm), InMemorySaver(), "你好")
        deltas = [e["data"]["text"] for e in events if e["event"] == "message.delta"]
        assert len(deltas) > 1 and "".join(deltas) == "你好 我是 SalesPilot"
        assert names(events)[-1] == "done"

    def test_crm_tool_error_is_reported(self, tool_ctx: ToolContext) -> None:
        # null session 让 service 失败，验证 tool.error 事件与兜底回复
        events = run_chat(
            make_deps(tool_ctx), InMemorySaver(), "帮我记一下：今天和明理律所通了电话"
        )
        seq = names(events)
        assert "tool.start" in seq and "tool.error" in seq and seq[-1] == "done"


def test_graph_exception_becomes_error_event(tool_ctx: ToolContext) -> None:
    class Boom:
        def stream(self, *args: Any, **kwargs: Any) -> Any:
            raise TimeoutError("slow")

    events = list(iter_graph_events(Boom(), {}, {}, "t9"))  # type: ignore[arg-type]
    assert names(events) == ["error", "done"]
    assert events[0]["data"]["code"] == 50401


def test_to_sse_keeps_chinese() -> None:
    msg = to_sse({"event": "message.delta", "data": {"text": "已为你生成"}})
    assert msg == {"event": "message.delta", "data": '{"text": "已为你生成"}'}
