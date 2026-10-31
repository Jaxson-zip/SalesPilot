"""确认后的写操作执行结果：回复和界面都按这里的状态走，不靠模型自己描述。

- done：已写入（卡片显示「已完成」和记录入口）
- failed：执行失败（显示原因，没有写入）
- cancelled：用户取消（没有写入）
"""

import re
from typing import Any, Literal

from app.agent.tools import ToolResult

ActionStatus = Literal["done", "failed", "cancelled"]

# 执行成功后模型还在让用户确认的说法：「请确认卡片」「确认后即写入」「待你确认」
_ASKS_CONFIRM = re.compile(
    r"请(?:你|您)?(?:点击)?确认|确认后(?:即|才|会|就)|待(?:你|您)?确认|确认卡片"
)


def _link(name: str, data: Any) -> str | None:
    """写入后的记录入口（前端路由）。"""
    d = data if isinstance(data, dict) else {}
    if name in ("add_followup", "digest_material"):
        cid = d.get("customer_id")
        return f"/customers/{cid}" if cid else None
    if name == "create_task":
        return "/dashboard"
    if name == "submit_expense":
        return "/expenses"
    if name == "update_opportunity_stage":
        return "/pipeline"
    if name == "decide_approval":
        return "/approvals"
    if name == "generate_quote" and d.get("id"):
        return f"/quotes/{d['id']}"
    return None


def action_result(name: str, decision: str, result: ToolResult) -> dict[str, Any]:
    status: ActionStatus = (
        "cancelled" if decision != "approve" else "done" if result.ok else "failed"
    )
    return {
        "action": name,
        "status": status,
        "summary": result.summary,
        "href": _link(name, result.data) if status == "done" else None,
    }


def status_text(res: dict[str, Any]) -> str:
    if res["status"] == "done":
        return f"已完成：{res['summary']}。"
    if res["status"] == "failed":
        return f"没有执行成功：{res['summary']}。没有写入数据，可以修改后重试。"
    return "已取消，没有写入任何数据。"


def contradicts(reply: str | None, res: dict[str, Any] | None) -> bool:
    """回复和执行状态矛盾：已经写入了，回复却还在让用户确认。"""
    return bool(reply and res and res["status"] == "done" and _ASKS_CONFIRM.search(reply))
