"""写操作确认卡片的预览（interrupt.preview）：把模型给的原始参数转成销售看得懂的字段。

字段名与前端 lib/interrupt-preview.ts 的 FIELDS 对应（金额为分，由前端格式化）。
只做只读查询（按 id 取名称），没有副作用：interrupt 恢复时节点会重跑。
查不到名称（id 不存在或无权限）时不报错，执行时 service 会返回真正的错误码。
"""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.agent.tools.base import ToolContext
from app.crm.models import Approval
from app.crm.schemas.finance import EXPENSE_TYPE_LABELS
from app.crm.schemas.opportunity import STAGE_LABELS
from app.crm.services import approval_service, customer_service
from app.crm.services import opportunity_service as opp_service
from app.rules.calculators import stay_nights

logger = logging.getLogger("core.agent")

TASK_TYPE_LABELS = {
    "call": "电话",
    "visit": "拜访",
    "email": "邮件",
    "meeting": "会议",
    "todo": "待办",
}


def _customer_name(ctx: ToolContext, customer_id: Any) -> str | None:
    if not customer_id:
        return None
    with ctx.session() as db:
        return customer_service.get_customer(db, ctx.user, uuid.UUID(str(customer_id))).name


def _opportunity_name(ctx: ToolContext, opportunity_id: Any) -> str | None:
    if not opportunity_id:
        return None
    with ctx.session() as db:
        return opp_service.get_opportunity(db, ctx.user, uuid.UUID(str(opportunity_id))).name


def _names(values: Any) -> str | None:
    return "、".join(str(v) for v in values) if values else None


def _trip(details: Any) -> str | None:
    """差旅行程摘要：住宿「北京 2 晚（10-01 至 10-03）」，交通「深圳 → 北京」。"""
    if not isinstance(details, dict):
        return None
    if details.get("city"):
        nights = stay_nights(details)
        span = f"（{details.get('check_in')} 至 {details.get('check_out')}）" if nights else ""
        return f"{details['city']} {nights} 晚{span}" if nights else str(details["city"])
    route = [details.get("from_city"), details.get("to_city")]
    return " → ".join(str(c) for c in route if c) or None


def _expense(ctx: ToolContext, a: dict[str, Any]) -> dict[str, Any]:
    return {
        "expense_type": EXPENSE_TYPE_LABELS.get(a.get("type", "entertainment"), a.get("type")),
        "amount": a.get("amount"),
        "occurred_on": a.get("occurred_on"),
        "trip": _trip(a.get("details")),
        "customer_name": _customer_name(ctx, a.get("customer_id")),
        "contacts": _names(a.get("contact_names")),
        "colleagues": _names(a.get("colleague_names")),
        "headcount": a.get("headcount"),
        "reason": a.get("reason"),
    }


def _stage(ctx: ToolContext, a: dict[str, Any]) -> dict[str, Any]:
    return {
        "opportunity_name": _opportunity_name(ctx, a.get("opportunity_id")),
        "stage": STAGE_LABELS.get(a.get("stage", ""), a.get("stage")),
        "lost_reason": a.get("lost_reason"),
    }


def _task(ctx: ToolContext, a: dict[str, Any]) -> dict[str, Any]:
    subject = a.get("subject_id")
    is_opp = a.get("subject_type") == "opportunity"
    due = a.get("due_at")
    try:
        due_text = datetime.fromisoformat(str(due)).strftime("%m-%d %H:%M") if due else None
    except ValueError:
        due_text = str(due)
    return {
        "task_title": a.get("title"),
        "due_at": due_text,
        "task_type": TASK_TYPE_LABELS.get(a.get("type", "todo"), a.get("type")),
        "opportunity_name" if is_opp else "customer_name": (
            _opportunity_name(ctx, subject) if is_opp else _customer_name(ctx, subject)
        ),
    }


def _approval_target(ctx: ToolContext, approval_id: Any) -> dict[str, Any]:
    """审批对象（单号、标题、金额），只读；只有主管看得到本团队的审批。"""
    if not approval_id:
        return {}
    with ctx.session() as db:
        approval = db.get(Approval, uuid.UUID(str(approval_id)))
        if approval is None or approval.team_id != ctx.user.team_id:
            return {}
        target = approval_service.to_items(db, [approval])[0].target
    return {"target": f"{target.code} {target.title}", "amount": target.amount}


def _approval(ctx: ToolContext, a: dict[str, Any]) -> dict[str, Any]:
    return {
        **_approval_target(ctx, a.get("approval_id")),
        "decision": "通过" if a.get("decision") == "approve" else "驳回",
        "comment": a.get("comment"),
    }


BUILDERS: dict[str, Callable[[ToolContext, dict[str, Any]], dict[str, Any]]] = {
    "submit_expense": _expense,
    "update_opportunity_stage": _stage,
    "create_task": _task,
    "decide_approval": _approval,
}


def confirm_preview(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    builder = BUILDERS.get(name)
    if builder is None:
        return {k: v for k, v in args.items() if not isinstance(v, (dict, list))}
    try:
        preview = builder(ctx, args)
    except Exception:  # 预览只是展示，查名称失败不能影响确认流程
        logger.warning("preview for %s failed", name, exc_info=True)
        return {k: v for k, v in args.items() if not isinstance(v, (dict, list))}
    return {k: v for k, v in preview.items() if v not in (None, "")}
