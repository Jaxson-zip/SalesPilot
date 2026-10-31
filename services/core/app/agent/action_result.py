"""确认后的写操作执行结果：回复和界面都按这里的状态走，不靠模型自己描述。

- done：已写入（卡片显示「已完成」和记录入口）
- failed：执行失败（显示原因，没有写入）
- cancelled：用户取消（没有写入）
"""

import re
from typing import Any, Literal

from app.agent.tools import ToolResult
from app.crm.services.notification_service import subject_link

ActionStatus = Literal["done", "failed", "cancelled"]

# 执行成功后模型还在让用户确认这次操作的说法：「请确认卡片」「确认后即写入」「待你确认」。
# 只认针对卡片 / 写入的说法，「请确认下周是否拜访」这类正常建议不算
_ASKS_CONFIRM = re.compile(
    r"确认卡片|点击确认|请(?:你|您)?确认(?:执行|写入|保存|提交|创建|操作|后)"
    r"|确认后(?:即|才|会|就|再|可){0,2}(?:写入|执行|保存|提交|创建|生效)|待(?:你|您)?确认"
)


def _link(name: str, data: Any) -> str | None:
    """写入后的记录入口（前端路由），直接打开刚写入的那条记录；拿不到 id 时退回列表页。"""
    d = data if isinstance(data, dict) else {}
    rid = d.get("id")
    if name in ("add_followup", "digest_material"):
        cid = d.get("customer_id")
        return f"/customers/{cid}" if cid else None
    if name == "create_task":
        if rid and d.get("subject_type") and d.get("subject_id"):
            link = subject_link(d["subject_type"], d["subject_id"])
            return f"{link}{'&' if '?' in link else '?'}task={rid}"
        return "/dashboard"
    if name == "submit_expense":
        return f"/expenses?id={rid}" if rid else "/expenses"
    if name == "update_opportunity_stage":
        return f"/pipeline?opp={rid}" if rid else "/pipeline"
    if name == "decide_approval":
        return f"/approvals?id={rid}" if rid else "/approvals"
    if name == "generate_quote" and rid:
        return f"/quotes/{rid}"
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
