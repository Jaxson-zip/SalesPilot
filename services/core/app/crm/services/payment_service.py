"""回款记录 service：登记回款（带到账日期、流水号、备注）、查看记录、冲正。

登记错了不改不删：冲正 = 另记一笔负数并写明原因，原记录、操作人、原因都保留，便于对账。
合同 paid_amount 随记录增减，已确认提成按回款比例重算（与登记回款同一规则）。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_role, ensure_same_team
from app.common.scope import ensure_visible
from app.crm.models import Commission, Contract, Payment
from app.crm.schemas.finance import ContractItem, PaymentIn, PaymentRecord
from app.crm.services import activity_service, contract_service, lookup
from app.crm.services.codes import local_today
from app.rules import confirm_commission

RULE_EXCEEDS_BALANCE = contract_service.RULE_EXCEEDS_BALANCE
RULE_ALREADY_REVERSED = "payment_already_reversed"
RULE_DUPLICATE_REFERENCE = "payment_duplicate_reference"


def _locked_contract(db: Session, user: CurrentUser, contract_id: uuid.UUID) -> Contract:
    ensure_role(user, Role.MANAGER, "仅销售主管可以登记和冲正回款")
    contract = db.get(Contract, contract_id, with_for_update=True)
    ensure_same_team(contract, user)
    assert contract is not None
    return contract


def _apply(db: Session, contract: Contract, delta: int) -> None:
    """已回款增减后：全部收齐为 paid，否则回到 active；已确认提成按回款比例重算。"""
    contract.paid_amount += delta
    contract.status = "paid" if contract.paid_amount >= contract.amount else "active"
    for c in db.scalars(select(Commission).where(Commission.contract_id == contract.id)):
        c.confirmed = confirm_commission(c.estimated, contract.paid_amount, contract.amount)
    db.flush()


def add_payment(
    db: Session, user: CurrentUser, contract_id: uuid.UUID, body: PaymentIn
) -> ContractItem:
    """登记回款（仅 manager 且合同属于本团队）。

    防重复：同一个 idempotency_key 的重试直接返回合同当前状态（第一次已入账、页面没收到响应）；
    银行流水号已经登记过（且没冲正）时拒绝，提示先核查。合同行锁保证两次请求排队检查。
    """
    contract = _locked_contract(db, user, contract_id)
    if _already_recorded(db, contract, body):
        return contract_service.get_contract(db, user, contract.id)
    _reject_duplicate_reference(db, body.reference_no)
    balance = contract.amount - contract.paid_amount
    if body.amount > balance:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"回款金额超过未回款余额 ¥{balance / 100:,.2f}",
            {"rule": RULE_EXCEEDS_BALANCE, "balance": balance},
        )
    received_on = body.received_on or local_today()
    db.add(
        Payment(
            contract_id=contract.id,
            amount=body.amount,
            received_on=received_on,
            reference_no=(body.reference_no or "").strip() or None,
            note=(body.note or "").strip() or None,
            created_by=user.id,
            idempotency_key=body.idempotency_key,
        )
    )
    _apply(db, contract, body.amount)
    ref = f"，流水号 {body.reference_no.strip()}" if body.reference_no else ""
    activity_service.record(
        db,
        user,
        "contract",
        contract.id,
        "payment",
        f"登记回款 ¥{body.amount / 100:,.2f}（{received_on:%m-%d} 到账{ref}），"
        f"累计回款 {contract.paid_amount / contract.amount:.0%}",
        subject=contract,
    )
    return contract_service.get_contract(db, user, contract.id)


def _already_recorded(db: Session, contract: Contract, body: PaymentIn) -> bool:
    """同一次登记的重试：内容一致返回 True（不再记账），内容不同报冲突。"""
    if not body.idempotency_key:
        return False
    done = db.scalar(select(Payment).where(Payment.idempotency_key == body.idempotency_key))
    if done is None:
        return False
    if done.contract_id != contract.id or done.amount != body.amount:
        raise BizError(
            ErrorCode.DUPLICATE,
            f"这次登记已经入账（¥{done.amount / 100:,.2f}），请刷新后核对回款记录",
        )
    return True


def _reject_duplicate_reference(db: Session, reference_no: str | None) -> None:
    """同一个银行流水号一般只对应一笔到账：已登记且没冲正的，拦下来让人核查。"""
    ref = (reference_no or "").strip()
    if not ref:
        return
    reversed_ids = select(Payment.reversal_of).where(Payment.reversal_of.is_not(None))
    stmt = select(Payment).where(
        Payment.reference_no == ref, Payment.amount > 0, Payment.id.not_in(reversed_ids)
    )
    found = db.scalars(stmt).first()
    if found is None:
        return
    contract = db.get(Contract, found.contract_id)
    raise BizError(
        ErrorCode.RULE_VIOLATION,
        f"流水号 {ref} 已登记过（{contract.code if contract else ''} ¥{found.amount / 100:,.2f}，"
        f"{found.received_on:%m-%d} 到账），请核查是否重复；如果是录错的那笔，先冲正再登记",
        {"rule": RULE_DUPLICATE_REFERENCE, "payment_id": str(found.id)},
    )


def reverse_payment(
    db: Session, user: CurrentUser, contract_id: uuid.UUID, payment_id: uuid.UUID, reason: str
) -> ContractItem:
    """冲正一笔回款：另记一笔负数（写明原因），原记录保留；一笔只能冲正一次，冲正记录不能再冲正。"""
    contract = _locked_contract(db, user, contract_id)
    original = db.get(Payment, payment_id, with_for_update=True)
    if original is None or original.contract_id != contract.id:
        raise BizError(ErrorCode.NOT_FOUND, "回款记录不存在")
    if original.reversal_of is not None or original.amount <= 0:
        raise BizError(ErrorCode.VALIDATION, "冲正记录不能再冲正")
    if db.scalar(select(Payment.id).where(Payment.reversal_of == original.id)):
        raise BizError(
            ErrorCode.RULE_VIOLATION, "这笔回款已经冲正过了", {"rule": RULE_ALREADY_REVERSED}
        )
    db.add(
        Payment(
            contract_id=contract.id,
            amount=-original.amount,
            received_on=local_today(),
            reference_no=original.reference_no,
            reversal_of=original.id,
            reason=reason.strip(),
            created_by=user.id,
        )
    )
    _apply(db, contract, -original.amount)
    activity_service.record(
        db,
        user,
        "contract",
        contract.id,
        "payment_reverse",
        f"冲正回款 ¥{original.amount / 100:,.2f}（{original.received_on:%m-%d} 到账那笔），"
        f"原因：{reason.strip()}",
        subject=contract,
    )
    return contract_service.get_contract(db, user, contract.id)


def list_payments(db: Session, user: CurrentUser, contract_id: uuid.UUID) -> list[PaymentRecord]:
    """合同的回款记录（新的在前）：能看合同的人都能看。"""
    contract = db.get(Contract, contract_id)
    ensure_visible(contract, user)
    rows = list(
        db.scalars(
            select(Payment)
            .where(Payment.contract_id == contract_id)
            .order_by(Payment.created_at.desc(), Payment.id)
        )
    )
    reversed_by = {r.reversal_of: r.id for r in rows if r.reversal_of}
    users = lookup.users(db, (r.created_by for r in rows))
    return [
        PaymentRecord(
            id=r.id,
            amount=r.amount,
            received_on=r.received_on,
            reference_no=r.reference_no,
            note=r.note,
            reversal_of=r.reversal_of,
            reversed_by=reversed_by.get(r.id),
            reason=r.reason,
            created_by=users.get(r.created_by) if r.created_by else None,
            created_at=r.created_at,
        )
        for r in rows
    ]
