"""商机 / 客户页的「下一步建议」：按这单的当前状态用规则算出来，不调模型。

每条建议带一句交给 AI 的话（prompt）：销售点「交给 AI」就带着这单打开 AI 工作台，
由 AI 去查、去写（写操作照常弹确认卡）。判断全部来自 DealState 里规则代码算好的字段
（停滞天数、赢单要素缺口、逾期金额等），阈值在 rules.yaml，这里不写死数字。
"""

import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.schemas.common import PageParams
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import customer_service
from app.crm.services import opportunity_service as opp_service
from app.crm.services.deal_state_service import DealState, get_deal_state

SuggestionKind = Literal[
    "overdue_payment",
    "quote_unsent",
    "stale",
    "task_overdue",
    "no_next_step",
    "meddic_gap",
    "no_quote",
    "competitor",
]


class DealSuggestion(BaseModel):
    kind: SuggestionKind
    level: Literal["warn", "info"]
    title: str
    detail: str | None = None
    prompt: str
    opportunity_id: uuid.UUID
    opportunity_name: str


def _yuan(cents: int) -> str:
    return f"{cents / 100:,.0f} 元"


def _money(s: DealState) -> list[tuple[SuggestionKind, str, str | None, str]]:
    out: list[tuple[SuggestionKind, str, str | None, str]] = []
    o = s.opportunity
    if (c := s.contract) and c.overdue_days:
        out.append((
            "overdue_payment",
            f"回款逾期 {c.overdue_days} 天",
            f"合同 {c.code} 有 {_yuan(c.overdue_amount)} 到期未回",
            f"{o.customer.name}的合同 {c.code} 回款逾期了，帮我记一条催款跟进并安排下一步",
        ))  # fmt: skip
    if (q := s.quote) and q.status == "approved":
        out.append((
            "quote_unsent",
            "报价已审批，还没发给客户",
            f"{q.code}，{_yuan(q.total_price)}",
            f"{o.name}的报价 {q.code} 已经审批了，帮我写一段发给客户的说明，并安排跟进时间",
        ))  # fmt: skip
    return out


def _activity(s: DealState) -> list[tuple[SuggestionKind, str, str | None, str]]:
    out: list[tuple[SuggestionKind, str, str | None, str]] = []
    o = s.opportunity
    if o.stale:
        out.append((
            "stale",
            f"已 {o.idle_days} 天没有动态",
            s.last_followup.content[:60] if s.last_followup else None,
            f"{o.name}已经 {o.idle_days} 天没动静了，帮我想想怎么重新约上客户，并安排下一步",
        ))  # fmt: skip
    if o.next_task and o.next_task.overdue:
        out.append((
            "task_overdue",
            "下一步已逾期",
            o.next_task.title,
            f"{o.name}的「{o.next_task.title}」逾期了，帮我看看现在该怎么推进",
        ))  # fmt: skip
    elif not o.next_task:
        out.append((
            "no_next_step",
            "还没有安排下一步",
            None,
            f"{o.name}下一步该做什么？结合现在的情况帮我安排",
        ))  # fmt: skip
    return out


def _deal(s: DealState) -> list[tuple[SuggestionKind, str, str | None, str]]:
    out: list[tuple[SuggestionKind, str, str | None, str]] = []
    o = s.opportunity
    if o.meddic_risks:
        gaps = "、".join(o.meddic_risks)
        out.append((
            "meddic_gap",
            f"当前阶段还没确认：{gaps}",
            None,
            f"{o.name}还没确认{gaps}，下一步该见谁、问什么？",
        ))  # fmt: skip
    if o.stage in ("proposal", "negotiation") and s.quote is None:
        out.append((
            "no_quote",
            "到了方案报价阶段，还没有报价",
            None,
            f"按{o.customer.name}的需求给{o.name}出方案和报价",
        ))  # fmt: skip
    if o.competitors:
        rivals = "、".join(o.competitors)
        out.append((
            "competitor",
            f"有竞品：{rivals}",
            None,
            f"{o.name}在和{rivals}竞争，我们该怎么打？",
        ))  # fmt: skip
    return out


WARN: frozenset[str] = frozenset({"overdue_payment", "stale", "task_overdue", "quote_unsent"})


def suggest(s: DealState) -> list[DealSuggestion]:
    """纯函数：按紧急程度排好（钱 → 动态 → 赢单要素 / 报价 / 竞品）。终态商机只看回款。"""
    o = s.opportunity
    rows = _money(s) if o.stage in FINAL_STAGES else [*_money(s), *_activity(s), *_deal(s)]
    return [
        DealSuggestion(
            kind=kind,
            level="warn" if kind in WARN else "info",
            title=title,
            detail=detail,
            prompt=prompt,
            opportunity_id=o.id,
            opportunity_name=o.name,
        )
        for kind, title, detail, prompt in rows
    ]


def opportunity_suggestions(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID
) -> list[DealSuggestion]:
    return suggest(get_deal_state(db, user, opportunity_id))


def customer_suggestions(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, limit: int = 6
) -> list[DealSuggestion]:
    """客户下各商机的建议汇总（警示在前）；客户看不到时 40401。"""
    customer_service.get_customer(db, user, customer_id)
    page = opp_service.list_opportunities(
        db, user, None, PageParams(page=1, page_size=20), customer_id=customer_id
    )
    rows: list[DealSuggestion] = []
    for o in page.items:
        if o.stage not in FINAL_STAGES or o.stage == "won":
            rows += opportunity_suggestions(db, user, o.id)
    rows.sort(key=lambda r: r.level != "warn")
    return rows[:limit]
