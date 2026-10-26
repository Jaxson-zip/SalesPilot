"""respond 节点的规则模板回复（网关不可用或出错时的兜底）。"""

from typing import Any

from app.agent.nodes.respond import template_reply


def _state(**kw: Any) -> Any:
    return kw


def test_quote_reply_uses_chinese_status_and_formatted_price() -> None:
    quote = {"code": "Q-2026-002", "total_price": 37_200_000, "status": "draft"}
    text = template_reply(_state(quote=quote))
    assert text == "报价单 Q-2026-002 已创建，总价 ¥372,000，状态：草稿。"


def test_quote_reply_pending_approval() -> None:
    quote = {"code": "Q-2026-003", "total_price": 29_800_000, "status": "pending_approval"}
    assert "待主管审批" in template_reply(_state(quote=quote))


def test_error_reply_contains_code() -> None:
    text = template_reply(_state(error={"code": 50001, "message": "数据库不可用"}))
    assert "50001" in text and "数据库不可用" in text


def test_greeting_when_nothing_happened() -> None:
    assert template_reply(_state()).startswith("你好，我是 SalesPilot")
