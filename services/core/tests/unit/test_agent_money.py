"""给模型看的金额：分 → 换算好的文字，模型直接引用。"""

import json

from app.agent.money import annotate_money, is_money_key, yuan_text
from app.agent.nodes.tool_loop import _tool_content
from app.agent.tools import ToolResult


def test_yuan_text() -> None:
    assert yuan_text(46_000_000) == "¥460,000（46 万元）"
    assert yuan_text(12_345_678) == "¥123,456.78（12.35 万元）"
    assert yuan_text(86_000) == "¥860"
    assert yuan_text(-10_000) == "-¥100"
    assert yuan_text(0) == "¥0"


def test_money_keys() -> None:
    for key in ("amount", "total_price", "unit_cost", "annual_budget", "won_amount_month"):
        assert is_money_key(key)
    for key in ("total", "qty", "win_rate", "overdue_days", "page_size", "headcount"):
        assert not is_money_key(key)


def test_annotate_nested_and_keeps_fen() -> None:
    data = {"items": [{"name": "质检助手", "amount": 46_000_000, "win_rate": 50}], "ok": True}
    out = annotate_money(data)
    item = out["items"][0]
    assert item["amount"] == 46_000_000 and item["amount_text"] == "¥460,000（46 万元）"
    assert "win_rate_text" not in item and out["ok"] is True


def test_tool_content_carries_amount_text() -> None:
    """回归：商机 ¥460,000 被模型自己换算成「460 万元」。"""
    result = ToolResult(ok=True, summary="找到 1 个商机", data={"amount": 46_000_000})
    payload = json.loads(_tool_content(result))
    assert payload["data"]["amount_text"] == "¥460,000（46 万元）"
