"""function calling 的纯逻辑：工具可见范围、系统注入参数、转入出方案、需求抽取的模型 / 规则切换。"""

from typing import Any

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.deps import AgentDeps
from app.agent.nodes.requirement_fields import extract_with_llm, optional_model
from app.agent.tools import TOOLS, ToolContext, chat_tools_for, inject_system_args, tools_for
from app.common.auth import Role
from app.packs.llm_deploy.requirement import LlmDeployRequirement
from tests.scripted_llm import ScriptedModel, call
from tests.unit.test_agent import SOLUTION_MSG, make_deps, names, run_chat


def _deps(ctx: ToolContext, llm: Any) -> AgentDeps:
    return AgentDeps(ctx=ctx, resolve_pack=lambda _o: "llm_deploy", llm=llm)


class TestToolExposure:
    def test_sales_cannot_see_approval_tool(self) -> None:
        names_ = {t.name for t in chat_tools_for(Role.SALES)}
        assert "decide_approval" not in names_ and "list_pending_approvals" not in names_
        assert {"submit_expense", "update_opportunity_stage", "get_customer_context"} <= names_

    def test_manager_sees_approval_tools(self) -> None:
        names_ = {t.name for t in chat_tools_for(Role.MANAGER)}
        assert {"decide_approval", "list_pending_approvals"} <= names_

    def test_admin_only_gets_read_only_tools(self) -> None:
        tools = chat_tools_for(Role.ADMIN)
        assert tools and all(not t.write for t in tools)

    def test_schema_hides_system_args(self) -> None:
        stage = TOOLS["update_opportunity_stage"].openai_schema()["function"]["parameters"]
        assert "idempotency_key" not in stage["properties"]
        assert "idempotency_key" not in stage["required"]
        policy = TOOLS["search_policy"].openai_schema()["function"]["parameters"]
        assert "pack_id" not in policy["properties"]

    def test_inject_overrides_model_values(self) -> None:
        spec = TOOLS["update_opportunity_stage"]
        args = {"stage": "won", "idempotency_key": "model-made-up", "pack_id": "it_office"}
        out = inject_system_args(spec, args, {"idempotency_key": "agent:t:c1", "pack_id": "x"})
        assert out["idempotency_key"] == "agent:t:c1"
        assert "pack_id" not in out  # 该工具没有 pack_id 参数，不注入


def _nodes(events: list[dict[str, Any]]) -> list[str]:
    return [e["data"]["node"] for e in events if e["event"] == "node.start"]


class TestEntry:
    """不单独做意图分类：每句话进对话循环，由带上下文的模型决定是否转入出方案。"""

    def test_model_hands_off_to_solution(self, tool_ctx: ToolContext) -> None:
        # 用户说「按刚才说的给他们出方案」，模型结合上文把需求说完整后转入出方案流程
        llm = ScriptedModel(script=[call("start_solution", {"request": SOLUTION_MSG}, "s1")])
        events = run_chat(make_deps(tool_ctx, llm=llm), InMemorySaver(), "按刚才说的给他们出方案")
        assert "start_solution" in llm.bound[0]
        assert _nodes(events)[:3] == ["router", "tool_agent", "start_solution"]
        assert "parse_requirement" in _nodes(events)
        (pending,) = [e["data"] for e in events if e["event"] == "interrupt"]
        assert pending["action"] == "generate_quote"  # 需求取自模型整理的完整描述
        assert "tool.start" in names(events)

    def test_chitchat_is_one_model_call(self, tool_ctx: ToolContext) -> None:
        llm = ScriptedModel(script=[AIMessage(content="你好，有什么要我帮忙的？")])
        events = run_chat(make_deps(tool_ctx, llm=llm), InMemorySaver(), "你好")
        assert len(llm.seen) == 1  # 没有单独的意图分类调用
        text = "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
        assert text == "你好，有什么要我帮忙的？"

    def test_model_down_still_routes_solution_by_keywords(self, tool_ctx: ToolContext) -> None:
        llm = ScriptedModel(script=[], fail=True)
        events = run_chat(make_deps(tool_ctx, llm=llm), InMemorySaver(), SOLUTION_MSG)
        assert "parse_requirement" in _nodes(events)
        assert [e["data"]["action"] for e in events if e["event"] == "interrupt"] == [
            "generate_quote"
        ]

    def test_handoff_tool_visibility(self) -> None:
        assert "start_solution" in {t.name for t in chat_tools_for(Role.SALES)}
        assert "start_solution" in {t.name for t in chat_tools_for(Role.ADMIN)}  # 只出方案
        assert "start_solution" not in {t.name for t in tools_for(Role.SALES, "learn")}


class TestRequirementExtraction:
    def test_optional_model_accepts_empty(self) -> None:
        assert optional_model(LlmDeployRequirement)().model_dump() == {
            "model_name": None,
            "concurrency": None,
            "scene": None,
            "budget": None,
            "context_tokens": None,
        }

    def test_keeps_only_mentioned_fields(self, tool_ctx: ToolContext) -> None:
        extracted = {"model_name": "Qwen3-32B", "concurrency": 50, "budget": None}
        llm = ScriptedModel(script=[call("LlmDeployRequirementExtract", extracted, "e1")])
        out = extract_with_llm(_deps(tool_ctx, llm), LlmDeployRequirement, "Qwen3-32B，50 人")
        assert out == {"model_name": "Qwen3-32B", "concurrency": 50}

    def test_failure_returns_empty(self, tool_ctx: ToolContext) -> None:
        llm = ScriptedModel(script=[], fail=True)
        assert extract_with_llm(_deps(tool_ctx, llm), LlmDeployRequirement, "随便") == {}


class TestFallback:
    def test_llm_down_falls_back_to_rules(self, tool_ctx: ToolContext) -> None:
        """模型第一次调用就失败：路由和工具选择都回落到关键词规则，事件流照常结束。"""
        llm = ScriptedModel(script=[], fail=True)
        deps = make_deps(tool_ctx, llm=llm)
        events = run_chat(deps, InMemorySaver(), "帮我查一下明理律所这个客户")
        starts = [e["data"]["name"] for e in events if e["event"] == "tool.start"]
        assert starts == ["search_customer"]
        assert names(events)[-1] == "done"

    def test_chitchat_without_tools(self, tool_ctx: ToolContext) -> None:
        llm = ScriptedModel(
            script=[
                AIMessage(content="请告诉我客户名称，我来帮你查。"),
            ]
        )
        events = run_chat(make_deps(tool_ctx, llm=llm), InMemorySaver(), "帮我查个客户")
        text = "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
        assert text == "请告诉我客户名称，我来帮你查。"  # 只输出一遍（respond 不再重复生成）
        assert "tool.start" not in names(events)


def test_write_key_differs_across_turns() -> None:
    """回归：有的厂商按序号给工具调用 id（functions.x:0），同一会话后面会再出现，
    幂等键不能因此命中前面那一笔（会把新的报销当成重复提交）。"""
    from app.agent.nodes.tool_loop import _system_args
    from app.crm.services.demo import DEMO_USERS

    ctx = ToolContext(user=DEMO_USERS[Role.SALES], session=None, thread_id="t-key")  # type: ignore[arg-type]
    deps = make_deps(ctx)
    one: Any = {"messages": [AIMessage(content="a")]}
    five: Any = {"messages": [AIMessage(content="a")] * 5}
    first = _system_args(deps, one, "functions.x:0")["idempotency_key"]
    later = _system_args(deps, five, "functions.x:0")["idempotency_key"]
    assert first != later and len(later) <= 100
