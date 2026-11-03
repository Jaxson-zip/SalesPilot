"""这单赚多少：报价毛利 − 预估提成 − 跟单费用（已批 + 审批中）。

- 成交后按客户接受的报价算（accepted）；还没成交按最新一张没被拒的报价估算（latest）；
- 已输单的不再按报价算收益（报价毛利、提成都没有发生），只剩已经花掉的跟单费用（lost）。
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crm.models import Expense, Opportunity, Quote
from app.crm.schemas.opportunity import OpportunityExpenses, OpportunityProfit


def expense_summary(db: Session, opportunity_id: uuid.UUID) -> OpportunityExpenses:
    """关联到这单的报销：已批准（含已付款）和审批中的金额，草稿和被驳回的不算。"""
    rows = db.execute(
        select(Expense.status, func.count(), func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.opportunity_id == opportunity_id)
        .where(Expense.status.in_(("pending_approval", "approved", "paid")))
        .group_by(Expense.status)
    ).all()
    out = OpportunityExpenses()
    for status, n, total in rows:
        out.count += n
        if status == "pending_approval":
            out.pending += int(total)
        else:
            out.approved += int(total)
    return out


def deal_profit(
    db: Session, opp: Opportunity, expenses: OpportunityExpenses
) -> OpportunityProfit | None:
    """这单赚多少；没有报价返回 None。"""
    # quote_service 依赖商机模块（推进阶段），放在函数里导入避免循环引用
    from app.crm.services.quote_service import estimated_commission

    quotes = db.scalars(
        select(Quote)
        .where(Quote.opportunity_id == opp.id, Quote.status != "rejected")
        .order_by(Quote.created_at.desc())
    ).all()
    if not quotes:
        return None
    accepted = next((q for q in quotes if q.status == "accepted"), None)
    quote = accepted or quotes[0]
    spent = expenses.approved + expenses.pending
    head = {"quote_id": quote.id, "quote_code": quote.code, "price": quote.total_price}
    if opp.stage == "lost":
        return OpportunityProfit(
            **head, basis="lost", gross=0, commission=0, expenses=spent, net=-spent
        )
    gross = quote.total_price - quote.total_cost
    commission = estimated_commission(db, quote)
    return OpportunityProfit(
        **head,
        basis="accepted" if accepted else "latest",
        gross=gross,
        commission=commission,
        expenses=spent,
        net=gross - commission - spent,
    )
