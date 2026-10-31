"""一单生意的当前状态：商机 + 最近一次跟进 + 最新报价 + 合同回款。

AI 每轮对话把它放进上下文（不用模型自己去查），商机页的「下一步建议」也基于它计算。
权限与商机详情一致：看不到的商机返回 40401。
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.models import Contract, Followup, PaymentPlan, Quote
from app.crm.schemas.opportunity import OpportunityItem
from app.crm.schemas.quote import QUOTE_STATUS_LABELS
from app.crm.services import opportunity_service as opp_service
from app.crm.services.codes import local_today
from app.crm.services.payment_plan import PlanInput, allocate

FOLLOWUP_LABELS = {"phone": "电话", "visit": "拜访", "wechat": "微信", "email": "邮件", "ai": "AI"}


class DealFollowup(BaseModel):
    at: datetime
    type_label: str
    content: str


class DealQuote(BaseModel):
    id: uuid.UUID
    code: str
    status: str
    status_label: str
    total_price: int
    margin_rate: float
    updated_at: datetime


class DealContract(BaseModel):
    id: uuid.UUID
    code: str
    amount: int
    paid_amount: int
    overdue_amount: int  # 已过期未回的金额
    overdue_days: int  # 最早一期逾期天数，0 为没有逾期


class DealState(BaseModel):
    opportunity: OpportunityItem
    last_followup: DealFollowup | None
    quote: DealQuote | None  # 这单最近更新的一张报价
    contract: DealContract | None


def _last_followup(db: Session, opp: OpportunityItem) -> DealFollowup | None:
    """这单的最近一次跟进；没有挂在商机上的，用客户层面的最近一次。"""
    at = func.coalesce(Followup.occurred_at, Followup.created_at)
    for where in (Followup.opportunity_id == opp.id, Followup.customer_id == opp.customer.id):
        f = db.scalars(select(Followup).where(where).order_by(at.desc()).limit(1)).first()
        if f is not None:
            return DealFollowup(
                at=f.occurred_at or f.created_at,
                type_label=FOLLOWUP_LABELS.get(f.type, f.type),
                content=f.content[:200],
            )
    return None


def _latest_quote(db: Session, opportunity_id: uuid.UUID) -> Quote | None:
    stmt = select(Quote).where(Quote.opportunity_id == opportunity_id)
    return db.scalars(stmt.order_by(Quote.updated_at.desc()).limit(1)).first()


def _contract(db: Session, opportunity_id: uuid.UUID) -> DealContract | None:
    stmt = (
        select(Contract)
        .join(Quote, Contract.quote_id == Quote.id)
        .where(Quote.opportunity_id == opportunity_id)
        .order_by(Contract.created_at.desc())
        .limit(1)
    )
    c = db.scalars(stmt).first()
    if c is None:
        return None
    plans = list(
        db.scalars(
            select(PaymentPlan).where(PaymentPlan.contract_id == c.id).order_by(PaymentPlan.seq)
        )
    )
    states = allocate(
        [PlanInput(p.name, p.amount, p.due_date) for p in plans], c.paid_amount, local_today()
    )
    overdue = [s for s in states if s.status == "overdue"]
    return DealContract(
        id=c.id,
        code=c.code,
        amount=c.amount,
        paid_amount=c.paid_amount,
        overdue_amount=sum(s.amount - s.paid for s in overdue),
        overdue_days=max((s.overdue_days for s in overdue), default=0),
    )


def get_deal_state(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> DealState:
    opp = opp_service.get_item(db, user, opportunity_id)
    q = _latest_quote(db, opp.id)
    quote = (
        DealQuote(
            id=q.id,
            code=q.code,
            status=q.status,
            status_label=QUOTE_STATUS_LABELS.get(q.status, q.status),
            total_price=q.total_price,
            margin_rate=q.margin_rate,
            updated_at=q.updated_at,
        )
        if q
        else None
    )
    return DealState(
        opportunity=opp,
        last_followup=_last_followup(db, opp),
        quote=quote,
        contract=_contract(db, opp.id),
    )
