"""调整回款计划（B9）：负责人改期次、金额、到期日；已经发生的业务不能被改掉。

- 各期合计必须等于合同金额；
- 已收齐的期次不能删、不能改金额和到期日（到账已经冲抵到这一期）；
- 收了一部分的期次不能删，金额不能低于已收；
- 已申请 / 已开票的期次不能删、不能改金额（发票金额已经定了）；
- 合同已有回款、逾期或开票时必须写变更原因；动态里保留原计划、新计划和原因。

前面的期次锁定后，已收的钱冲抵到哪一期就不会因为调整计划而变。
"""

import uuid

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.crm.models import Contract, PaymentPlan
from app.crm.schemas.finance import PaymentPlanLineIn, PaymentPlanUpdate, PaymentPlanView
from app.crm.services import activity_service
from app.crm.services.contract_service import (
    get_payment_plan,
    invoice_fields,
    plans_of,
    states_of,
)
from app.crm.services.payment_plan import PlanState

RULE_PLAN_TOTAL = "plan_total_mismatch"
RULE_PLAN_INVOICED = "plan_invoiced"
RULE_PLAN_PAID = "plan_paid_locked"
RULE_PLAN_REASON = "plan_reason_required"


def _violation(message: str, rule: str, **extra: object) -> BizError:
    return BizError(ErrorCode.RULE_VIOLATION, message, {"rule": rule, **extra})


def _check_total(contract: Contract, items: list[PaymentPlanLineIn]) -> None:
    total = sum(i.amount for i in items)
    if total != contract.amount:
        raise _violation(
            f"各期合计 ¥{total / 100:,.2f}，与合同金额 ¥{contract.amount / 100:,.2f} 不一致",
            RULE_PLAN_TOTAL,
            expected=contract.amount,
            actual=total,
        )


def _check_period(
    seq: int, old: PaymentPlan, state: PlanState, new: PaymentPlanLineIn | None
) -> None:
    """按期次位置对比：第 seq 期改成了什么（None = 删掉了）。"""
    if state.status == "paid" and (
        new is None or (new.amount, new.due_date) != (old.amount, old.due_date)
    ):
        raise _violation(
            f"「{old.name}」已收齐，不能删除或修改金额、到期日", RULE_PLAN_PAID, seq=seq
        )
    if state.paid > 0 and (new is None or new.amount < state.paid):
        raise _violation(
            f"「{old.name}」已收 ¥{state.paid / 100:,.2f}，不能删除，金额也不能低于已收",
            RULE_PLAN_PAID,
            seq=seq,
        )
    if old.invoice_status != "none" and (new is None or new.amount != old.amount):
        raise _violation(
            f"「{old.name}」已申请或已开票，不能删除或修改金额；需要改请先让主管作废发票",
            RULE_PLAN_INVOICED,
            seq=seq,
        )


def needs_reason(contract: Contract, plans: list[PaymentPlan], states: list[PlanState]) -> bool:
    """合同已经有回款、逾期或开票：改计划要写原因（与前端 planNeedsReason 一致）。"""
    return (
        contract.paid_amount > 0
        or any(s.status == "overdue" for s in states)
        or any(p.invoice_status != "none" for p in plans)
    )


def _describe(rows: list[tuple[str, int, object]]) -> str:
    return "；".join(f"{n} ¥{a / 100:,.0f}（{d}）" for n, a, d in rows)


def _record(
    db: Session,
    user: CurrentUser,
    contract: Contract,
    old: list[PaymentPlan],
    data: PaymentPlanUpdate,
) -> None:
    before = _describe([(p.name, p.amount, p.due_date) for p in old])
    after = _describe([(i.name, i.amount, i.due_date) for i in data.items])
    text = f"原计划：{before}\n新计划：{after}"
    if data.reason and data.reason.strip():
        text += f"\n原因：{data.reason.strip()}"
    activity_service.record(
        db, user, "contract", contract.id, "payment_plan", text, subject=contract
    )


def _replace_rows(
    db: Session, contract: Contract, old: list[PaymentPlan], items: list[PaymentPlanLineIn]
) -> None:
    kept = {p.seq: invoice_fields(p) for p in old}  # 开票信息按期次带过去
    for p in old:
        db.delete(p)
    db.flush()
    for seq, item in enumerate(items, start=1):
        db.add(
            PaymentPlan(
                contract_id=contract.id,
                seq=seq,
                name=item.name.strip(),
                amount=item.amount,
                due_date=item.due_date,
                owner_id=contract.owner_id,
                team_id=contract.team_id,
                **kept.get(seq, {}),
            )
        )
    db.flush()


def replace_payment_plan(
    db: Session, user: CurrentUser, contract_id: uuid.UUID, data: PaymentPlanUpdate
) -> PaymentPlanView:
    contract = db.get(Contract, contract_id, with_for_update=True)
    ensure_owner(contract, user)
    assert contract is not None
    _check_total(contract, data.items)
    old = plans_of(db, [contract.id])[contract.id]
    states = states_of(contract, old)
    for p, s in zip(old, states, strict=True):
        _check_period(p.seq, p, s, data.items[p.seq - 1] if p.seq <= len(data.items) else None)
    if needs_reason(contract, old, states) and not (data.reason and data.reason.strip()):
        raise _violation("这份合同已有回款、逾期或开票，调整计划要写明原因", RULE_PLAN_REASON)
    _record(db, user, contract, old, data)
    _replace_rows(db, contract, old, data.items)
    return get_payment_plan(db, user, contract.id)
