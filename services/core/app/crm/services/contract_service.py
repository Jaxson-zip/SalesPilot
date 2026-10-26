"""合同与提成 service（接口契约 §4）：列表（含汇总）、详情、登记回款并按回款比例确认提成。"""

import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_role, ensure_same_team
from app.common.scope import View, apply_scope, ensure_visible
from app.crm.models import Commission, Contract, Quote
from app.crm.schemas.common import CodeRef, PageParams
from app.crm.schemas.finance import (
    CommissionBrief,
    ContractItem,
    ContractList,
    ContractSummary,
)
from app.crm.services import activity_service, lookup, quote_query
from app.crm.services.codes import month_start
from app.rules import confirm_commission, paid_ratio_of

RULE_EXCEEDS_BALANCE = "payment_exceeds_balance"


def _commissions(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, CommissionBrief]:
    if not ids:
        return {}
    stmt = (
        select(
            Commission.contract_id, func.sum(Commission.estimated), func.sum(Commission.confirmed)
        )
        .where(Commission.contract_id.in_(ids))
        .group_by(Commission.contract_id)
    )
    return {
        cid: CommissionBrief(estimated=int(e or 0), confirmed=int(c or 0))
        for cid, e, c in db.execute(stmt).all()
    }


def _quote_refs(db: Session, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, CodeRef]:
    wanted = [i for i in ids if i is not None]
    if not wanted:
        return {}
    rows = db.execute(select(Quote.id, Quote.code).where(Quote.id.in_(wanted))).all()
    return {r.id: CodeRef(id=r.id, code=r.code) for r in rows}


def to_items(db: Session, contracts: list[Contract]) -> list[ContractItem]:
    commissions = _commissions(db, [c.id for c in contracts])
    quotes = _quote_refs(db, [c.quote_id for c in contracts])
    customers = lookup.customers(db, (c.customer_id for c in contracts))
    owners = lookup.users(db, (c.owner_id for c in contracts))
    return [
        ContractItem(
            id=c.id,
            code=c.code,
            customer=lookup.pick(customers, c.customer_id),
            quote=lookup.pick(quotes, c.quote_id),
            amount=c.amount,
            paid_amount=c.paid_amount,
            paid_ratio=paid_ratio_of(c.paid_amount, c.amount),
            status=c.status,  # type: ignore[arg-type]
            commission=commissions.get(c.id, CommissionBrief(estimated=0, confirmed=0)),
            owner=lookup.pick(owners, c.owner_id),
            created_at=c.created_at,
        )
        for c in contracts
    ]


def _summary(db: Session, scoped: Select[Any]) -> ContractSummary:
    ids = scoped.with_only_columns(Contract.id)
    agg = select(
        func.coalesce(func.sum(Contract.amount - Contract.paid_amount), 0),
        func.coalesce(func.sum(Contract.amount).filter(Contract.created_at >= month_start()), 0),
    ).where(Contract.id.in_(ids))
    unpaid, month_amount = db.execute(agg).one()
    commission = select(
        func.coalesce(func.sum(Commission.estimated), 0),
        func.coalesce(func.sum(Commission.confirmed), 0),
    ).where(Commission.contract_id.in_(ids))
    estimated, confirmed = db.execute(commission).one()
    return ContractSummary(
        month_amount=int(month_amount),
        estimated_commission=int(estimated),
        confirmed_commission=int(confirmed),
        unpaid_amount=int(unpaid),
    )


def list_contracts(
    db: Session, user: CurrentUser, view: View | None, page: PageParams, status: str | None = None
) -> ContractList:
    """summary 按数据范围统计全部合同（不受 status 筛选影响）。"""
    scoped = apply_scope(select(Contract), Contract, user, view)
    stmt = scoped.where(Contract.status == status) if status else scoped
    total = quote_query.count(db, stmt)
    stmt = stmt.order_by(Contract.created_at.desc(), Contract.id)
    rows = list(db.scalars(stmt.offset(page.offset).limit(page.page_size)).all())
    return ContractList(items=to_items(db, rows), total=total, summary=_summary(db, scoped))


def get_contract(db: Session, user: CurrentUser, contract_id: uuid.UUID) -> ContractItem:
    db.flush()
    contract = db.get(Contract, contract_id)
    ensure_visible(contract, user)
    assert contract is not None
    db.refresh(contract)
    return to_items(db, [contract])[0]


def add_payment(
    db: Session, user: CurrentUser, contract_id: uuid.UUID, amount: int
) -> ContractItem:
    """登记回款（仅 manager 且合同属于本团队）：已确认提成 = 预估 × 回款比例；全部回款后为 paid。"""
    ensure_role(user, Role.MANAGER, "仅销售主管可以登记回款")
    contract = db.get(Contract, contract_id, with_for_update=True)
    ensure_same_team(contract, user)
    assert contract is not None
    if amount <= 0:
        raise BizError(ErrorCode.VALIDATION, "回款金额必须大于 0")
    balance = contract.amount - contract.paid_amount
    if amount > balance:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"回款金额超过未回款余额 ¥{balance / 100:,.2f}",
            {"rule": RULE_EXCEEDS_BALANCE, "balance": balance},
        )
    contract.paid_amount += amount
    if contract.paid_amount >= contract.amount:
        contract.status = "paid"
    for c in db.scalars(select(Commission).where(Commission.contract_id == contract.id)):
        c.confirmed = confirm_commission(c.estimated, contract.paid_amount, contract.amount)
    db.flush()
    activity_service.record(
        db,
        user,
        "contract",
        contract.id,
        "payment",
        f"登记回款 ¥{amount / 100:,.2f}，累计回款 {contract.paid_amount / contract.amount:.0%}",
        subject=contract,
    )
    return get_contract(db, user, contract.id)
