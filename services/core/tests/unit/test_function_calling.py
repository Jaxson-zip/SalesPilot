"""function calling 的纯逻辑：工具可见范围、系统注入参数、意图分类与需求抽取的模型 / 规则切换。"""

from typing import Any

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.deps import AgentDeps
from app.agent.nodes.requirement_fields import extract_with_llm, optional_model
from app.agent.nodes.router import llm_intent
from app.agent.tools import TOOLS, ToolContext, chat_tools_for, inject_system_args
from app.common.auth import Role
from app.packs.llm_deploy.requirement import LlmDeployRequirement
from tests.scripted_llm import ScriptedModel, call
from tests.unit.test_agent import make_deps, names, run_chat


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


class TestRouter:
    def test_llm_decides_intent(self, tool_ctx: ToolContext) -> None:
        llm = ScriptedModel(script=[call("IntentDecision", {"intent": "solution"}, "r1")])
        assert llm_intent(_deps(tool_ctx, llm), "帮我看看 32B 要几张卡", False) == "solution"

    def test_llm_failure_returns_none(self, tool_ctx: ToolContext) -> None:
        deps = _deps(tool_ctx, ScriptedModel(script=[], fail=True))
        assert llm_intent(deps, "你好", False) is None

    def test_no_llm_returns_none(self, tool_ctx: ToolContext) -> None:
        assert llm_intent(_deps(tool_ctx, None), "你好", False) is None


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
                call("IntentDecision", {"intent": "crm_action"}, "r1"),
                AIMessage(content="请告诉我客户名称，我来帮你查。"),
            ]
        )
        events = run_chat(make_deps(tool_ctx, llm=llm), InMemorySaver(), "帮我查个客户")
        text = "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
        assert text == "请告诉我客户名称，我来帮你查。"  # 只输出一遍（respond 不再重复生成）
        assert "tool.start" not in names(events)
