"""运行信息：当前时间、这一轮实际用的模型写进系统提示；闲聊直接回答，不再复述自我介绍。"""

from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage

from app.agent.nodes.respond import _chat_messages, is_chitchat, rule_chitchat, template_reply
from app.agent.runtime import ModelInfo, model_text, now_text, resolve_model, runtime_note

CARDS: list[dict[str, Any]] = [
    {"id": "deepseek-chat", "type": "model", "available": True},
    {"id": "hunyuan-turbo", "type": "model", "available": False},
    {
        "id": "chat-agent",
        "type": "group",
        "available": True,
        "members": ["hunyuan-turbo", "deepseek-chat", "qwen-plus"],
        "available_members": ["deepseek-chat", "qwen-plus"],
    },
]


def test_now_text_is_beijing_time_with_weekday() -> None:
    # 2026-10-30 07:42 UTC = 北京时间 15:42，周五
    assert (
        now_text(datetime(2026, 10, 30, 7, 42, tzinfo=UTC)) == "2026-10-30 星期五 15:42（北京时间）"
    )


def test_group_resolves_to_first_available_member() -> None:
    info = resolve_model("chat-agent", CARDS)
    assert info == ModelInfo(selected="chat-agent", served="deepseek-chat", fallbacks=["qwen-plus"])
    text = model_text(info)
    assert "深度求索 DeepSeek" in text and "deepseek-chat" in text
    assert "chat-agent" in text and "qwen-plus" in text


def test_single_model_and_unavailable() -> None:
    assert resolve_model("deepseek-chat", CARDS).served == "deepseek-chat"
    assert resolve_model("hunyuan-turbo", CARDS).served is None
    assert resolve_model("nope", CARDS).served is None
    assert "没有接入大模型" in model_text(None)
    # 不认识的别名只报别名，不编厂商
    assert model_text(ModelInfo("my-llm", "my-llm")).startswith("这一轮由 网关别名为 my-llm 的模型")


def test_runtime_note_has_time_and_model() -> None:
    note = runtime_note(
        ModelInfo("deepseek-chat", "deepseek-chat"), datetime(2026, 10, 30, 7, 42, tzinfo=UTC)
    )
    assert "15:42" in note and "deepseek-chat" in note and "不要声称自己是其他公司的模型" in note


def test_chitchat_messages_have_no_canned_reply() -> None:
    state: Any = {"intent": "chitchat", "messages": [HumanMessage("现在几点")]}
    assert is_chitchat(state)
    msgs = _chat_messages(state, runtime_note(None))
    assert "运行信息" in str(msgs[0].content) and "闲聊和业务以外的问题" in str(msgs[0].content)
    assert all("参考回复" not in str(m.content) for m in msgs)
    assert msgs[-1].content == "现在几点"
    assert not is_chitchat({"intent": "chitchat", "tool_log": [{"tool": "x"}]})  # type: ignore[typeddict-item]


def test_rule_fallback_answers_time_and_model_truthfully() -> None:
    assert (rule_chitchat("现在几点了") or "").startswith("现在是 ")
    assert "没有接入大模型" in (rule_chitchat("你是什么模型") or "")
    assert rule_chitchat("你好") is None
    assert template_reply({"intent": "chitchat", "user_message": "今天几号"}).startswith("现在是 ")  # type: ignore[typeddict-item]
    assert template_reply({"intent": "chitchat", "user_message": "你好"}).startswith(
        "你好，我是 SalesPilot"
    )  # type: ignore[typeddict-item]
