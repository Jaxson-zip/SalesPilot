"""写工具弹确认卡之前的业务预检：注定会失败的操作直接告诉模型原因，不让用户白点一次确认。

回归：标赢单却没给报价时，原来先弹「确认赢单」卡片，用户点了确认才报错。
"""

import uuid
from typing import Any

from app.agent.tools.base import ToolContext, ToolResult
from app.common.errors import BizError
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import opportunity_service, won_rule


def _won_needs_quote(ctx: ToolContext, args: dict[str, Any]) -> None:
    if args.get("stage") != "won" or args.get("quote_id"):
        return
    with ctx.session() as db:
        opp = opportunity_service.get_owned(db, ctx.user, uuid.UUID(str(args["opportunity_id"])))
        if opp.stage not in FINAL_STAGES:
            won_rule.reject_won_without_quote(db, opp)


CHECKS = {"update_opportunity_stage": _won_needs_quote}


def precheck(ctx: ToolContext, name: str, args: dict[str, Any]) -> ToolResult | None:
    """返回 None 表示可以弹确认卡；否则返回失败结果（直接作为工具结果交给模型）。"""
    check = CHECKS.get(name)
    if check is None:
        return None
    try:
        check(ctx, args)
    except BizError as exc:
        error: dict[str, Any] = {"code": exc.code, "message": exc.message, "data": exc.data}
        return ToolResult(ok=False, summary=exc.message, error=error)
    except (KeyError, ValueError):
        return None  # 参数不全 / 格式不对：交给确认后的正式校验报错
    return None
