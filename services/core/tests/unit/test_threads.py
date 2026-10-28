"""会话历史（checkpoint → 消息列表）与行业包详情：离线可跑（内存 checkpointer，不连数据库）。"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.history import PENDING_TEXT, read_thread_messages
from app.agent.threads import TITLE_MAX_CHARS, make_title, touch_thread
from app.agent.tools import ToolContext
from app.common.auth import Role
from app.common.errors import BizError
from app.crm.services import pack_service
from app.crm.services.demo import DEMO_USERS
from tests.unit.test_agent import SOLUTION_MSG, make_deps, run_chat, run_resume


def test_make_title() -> None:
    assert make_title("  你好\n\n世界 ") == "你好 世界"
    assert make_title("   ") == "新对话"
    assert len(make_title("字" * 100)) == TITLE_MAX_CHARS


def test_touch_thread_skips_null_session(tool_ctx: ToolContext) -> None:
    touch_thread(tool_ctx.session, tool_ctx.user, "t-x", "你好", None)  # 不抛异常


class TestHistory:
    def test_empty_thread_returns_empty(self, tool_ctx: ToolContext) -> None:
        out = read_thread_messages(None, tool_ctx.user, "t-none", InMemorySaver())
        assert out.thread_id == "t-none" and out.messages == [] and out.pending is None

    def test_pending_interrupt_then_resume(self, tool_ctx: ToolContext, fake_quotes: None) -> None:
        saver, deps = InMemorySaver(), make_deps(tool_ctx)
        run_chat(deps, saver, SOLUTION_MSG)
        out = read_thread_messages(None, tool_ctx.user, tool_ctx.thread_id, saver)
        assert [m.role for m in out.messages] == ["user", "assistant"]
        assert out.messages[0].text == SOLUTION_MSG and out.messages[0].created_at is not None
        # 确认前已流式输出方案说明，历史里就是这段说明（不再是占位文字）
        assert out.messages[1].text != PENDING_TEXT and "推荐" in out.messages[1].text
        assert [a.type for a in out.messages[1].artifacts] == ["solution_tiers", "bom"]
        assert out.pending is not None and out.pending["action"] == "generate_quote"

        run_resume(deps, saver, "approve")
        out = read_thread_messages(None, tool_ctx.user, tool_ctx.thread_id, saver)
        assert out.pending is None
        assert [m.role for m in out.messages] == ["user", "assistant"]
        reply = out.messages[1]
        assert "Q-2026-001" in reply.text and reply.created_at is not None
        assert reply.text.startswith("按需求")  # 方案说明与确认后的结果合成一条
        assert [a.type for a in reply.artifacts] == ["solution_tiers", "bom", "quote"]

    def test_ask_user_and_chitchat_text_only(self, tool_ctx: ToolContext) -> None:
        saver, deps = InMemorySaver(), make_deps(tool_ctx)
        run_chat(deps, saver, "帮我出一个 Qwen3-32B 私有化方案")
        run_chat(deps, saver, "你好")
        out = read_thread_messages(None, tool_ctx.user, tool_ctx.thread_id, saver)
        assert [m.role for m in out.messages] == ["user", "assistant", "user", "assistant"]
        assert "并发" in out.messages[1].text
        assert all(m.artifacts == [] for m in out.messages)

    def test_other_user_gets_404(self, tool_ctx: ToolContext) -> None:
        saver = InMemorySaver()
        run_chat(make_deps(tool_ctx), saver, "你好")
        with pytest.raises(BizError) as exc:
            read_thread_messages(None, DEMO_USERS[Role.MANAGER], tool_ctx.thread_id, saver)
        assert exc.value.code == 40401


class TestPackDetail:
    @pytest.mark.parametrize("pack_id", ["llm_deploy", "it_office"])
    def test_installed_packs(self, pack_id: str) -> None:
        detail = pack_service.get_pack_detail(pack_id)
        assert detail.id == pack_id and detail.name and detail.version
        assert detail.catalog and all(isinstance(i.price, int) for i in detail.catalog)
        assert detail.rules["margin"]["floor_rate"] == 0.25
        assert "pack" in detail.rules and "commission" in detail.rules
        assert detail.knowledge and all(d.size > 0 for d in detail.knowledge)

    def test_markdown_title_from_heading(self) -> None:
        docs = {d.doc_name: d for d in pack_service.get_pack_detail("llm_deploy").knowledge}
        assert docs["models.json"].title == "models"
        assert docs["vLLM部署规范.md"].title

    def test_not_installed(self) -> None:
        with pytest.raises(BizError) as exc:
            pack_service.get_pack_detail("no_such_pack")
        assert exc.value.code == 40401
