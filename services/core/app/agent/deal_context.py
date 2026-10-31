"""每轮放进 AI 上下文的「当前这单」：从 CRM 读出来的状态，不靠模型记聊天记录。

会话关联了商机时给商机全貌（阶段、下一步、最近跟进、赢单要素缺口、报价、回款）；
只关联了客户时给客户和它的进行中商机。读不到（无权限、已删除）就不放，不影响对话。
"""

import logging
import uuid
from datetime import datetime

from app.agent.tools.base import ToolContext
from app.crm.schemas.common import PageParams
from app.crm.schemas.opportunity import FINAL_STAGES, STAGE_LABELS
from app.crm.services import customer_service
from app.crm.services import opportunity_service as opp_service
from app.crm.services.deal_state_service import DealState, get_deal_state
from app.rules.crm_calc import LOCAL_TZ

logger = logging.getLogger("core.agent")

HEAD = "## 当前这单（CRM 里的最新数据，比聊天记录准；调用工具时直接用这里的 id，不必再查）"


def _yuan(cents: int) -> str:
    return f"{cents / 100:,.0f} 元"


def _day(moment: datetime) -> str:
    return moment.astimezone(LOCAL_TZ).strftime("%m-%d")


def deal_lines(s: DealState) -> list[str]:
    o = s.opportunity
    close = f"，预计 {o.expected_close_date:%m-%d} 成交" if o.expected_close_date else ""
    lines = [
        f"- 商机：{o.name}（客户：{o.customer.name}），阶段「{STAGE_LABELS[o.stage]}」，"
        f"金额 {_yuan(o.amount)}，赢率 {o.win_rate}%{close}",
        f"- 商机 id：{o.id}；客户 id：{o.customer.id}",
    ]
    if o.stage in FINAL_STAGES:
        lines.append(f"- 已{STAGE_LABELS[o.stage]}，阶段不能再改")
    elif o.next_task:
        late = "，已逾期" if o.next_task.overdue else ""
        lines.append(f"- 下一步：{o.next_task.title}（{_day(o.next_task.due_at)} 到期{late}）")
    else:
        lines.append("- 下一步：没有安排")
    if f := s.last_followup:
        lines.append(f"- 最近跟进：{_day(f.at)} {f.type_label}：{f.content}")
    if o.stale:
        lines.append(f"- 已 {o.idle_days} 天没有动态，属于停滞商机")
    if o.meddic_risks:
        lines.append(f"- 当前阶段还没确认的赢单要素：{'、'.join(o.meddic_risks)}")
    if o.competitors:
        lines.append(f"- 竞品：{'、'.join(o.competitors)}")
    if q := s.quote:
        lines.append(
            f"- 最新报价：{q.code}「{q.status_label}」，{_yuan(q.total_price)}，"
            f"毛利 {q.margin_rate:.1%}"
        )
    if c := s.contract:
        overdue = (
            f"，逾期未回 {_yuan(c.overdue_amount)}（{c.overdue_days} 天）" if c.overdue_days else ""
        )
        lines.append(
            f"- 合同：{c.code}，已回款 {_yuan(c.paid_amount)} / {_yuan(c.amount)}{overdue}"
        )
    return lines


def _customer_lines(ctx: ToolContext, customer_id: uuid.UUID) -> list[str]:
    with ctx.session() as db:
        customer = customer_service.get_customer(db, ctx.user, customer_id)
        opps = opp_service.list_opportunities(
            db, ctx.user, None, PageParams(page=1, page_size=10), customer_id=customer_id
        ).items
    lines = [f"- 客户：{customer.name}（等级 {customer.level or '未定'}），客户 id：{customer.id}"]
    active = [o for o in opps if o.stage not in FINAL_STAGES]
    for o in active[:5]:
        lines.append(
            f"- 进行中商机：{o.name}「{STAGE_LABELS[o.stage]}」{_yuan(o.amount)}，商机 id：{o.id}"
        )
    if not active:
        lines.append("- 没有进行中的商机")
    return lines


def deal_brief(ctx: ToolContext, opportunity_id: str | None, customer_id: str | None) -> str | None:
    """会话关联的商机 / 客户的状态文字；都没有或读取失败返回 None。"""
    try:
        if opportunity_id:
            with ctx.session() as db:
                state = get_deal_state(db, ctx.user, uuid.UUID(opportunity_id))
            return "\n".join([HEAD, *deal_lines(state)])
        if customer_id:
            return "\n".join([HEAD, *_customer_lines(ctx, uuid.UUID(customer_id))])
    except Exception:
        logger.warning("deal_brief failed opp=%s customer=%s", opportunity_id, customer_id)
    return None
