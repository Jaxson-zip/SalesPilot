"""开票跟踪（回款计划的每一期）：ToB 客户通常先要发票再付款。

- request：合同负责人申请开票（选专票 / 普票，可写抬头、税号等备注），通知本团队主管；
- issue：主管登记已开票（发票号码、开票日期），通知负责人；也可以不经申请直接登记；
- void：主管作废（红冲或撤回申请），回到未开票，通知负责人。
已开票但还没收齐的金额在回款计划和合同列表里单独提示。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner, ensure_role, ensure_same_team
from app.crm.models import Contract, PaymentPlan
from app.crm.schemas.finance import InvoiceIn, PaymentPlanView
from app.crm.services import activity_service, contract_service, notification_service
from app.crm.services.codes import local_today

RULE_INVOICE_STATE = "invoice_bad_state"
TYPE_NAMES = {"special": "专票", "normal": "普票"}
# 每个操作允许的当前状态
ALLOWED = {"request": ("none",), "issue": ("none", "requested"), "void": ("requested", "issued")}


def _plan(db: Session, contract: Contract, seq: int) -> PaymentPlan:
    plan = db.scalar(
        select(PaymentPlan)
        .where(PaymentPlan.contract_id == contract.id, PaymentPlan.seq == seq)
        .with_for_update()
    )
    if plan is None:
        raise BizError(ErrorCode.NOT_FOUND, f"合同 {contract.code} 没有第 {seq} 期")
    return plan


def act(
    db: Session, user: CurrentUser, contract_id: uuid.UUID, seq: int, body: InvoiceIn
) -> PaymentPlanView:
    contract = db.get(Contract, contract_id)
    if body.action == "request":
        ensure_owner(contract, user)
    else:
        ensure_role(user, Role.MANAGER, "开票登记由主管操作")
        ensure_same_team(contract, user)
    assert contract is not None
    plan = _plan(db, contract, seq)
    if plan.invoice_status not in ALLOWED[body.action]:
        state = {"none": "未开票", "requested": "已申请", "issued": "已开票"}[plan.invoice_status]
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"「{plan.name}」当前{state}，不能执行这个操作",
            {"rule": RULE_INVOICE_STATE, "status": plan.invoice_status},
        )
    what = f"{contract.code} {plan.name} ¥{plan.amount / 100:,.0f}"
    link = f"/contracts?plan={contract.id}"
    if body.action == "request":
        plan.invoice_status = "requested"
        plan.invoice_type = body.invoice_type or "special"
        plan.invoice_note = (body.note or "").strip() or None
        plan.invoice_requested_at = datetime.now(UTC)
        content = f"申请开票：{what}（{TYPE_NAMES[plan.invoice_type]}）"
        notification_service.notify(
            db,
            notification_service.team_managers(db, contract.team_id),
            "invoice_requested",
            f"开票申请：{what}",
            f"{user.name} 申请开{TYPE_NAMES[plan.invoice_type]}"
            + (f"；备注：{plan.invoice_note}" if plan.invoice_note else ""),
            link,
        )
    elif body.action == "issue":
        no = (body.invoice_no or "").strip()
        if not no:
            raise BizError(ErrorCode.VALIDATION, "请填写发票号码")
        plan.invoice_status = "issued"
        plan.invoice_type = body.invoice_type or plan.invoice_type or "special"
        plan.invoice_no = no
        plan.invoiced_on = body.invoiced_on or local_today()
        content = f"已开票：{what}（{TYPE_NAMES[plan.invoice_type]} {no}）"
        notification_service.notify(
            db, [contract.owner_id], "invoice_issued", f"已开票：{what}", f"发票号码 {no}", link
        )
    else:
        old = plan.invoice_no
        for f in contract_service.INVOICE_FIELDS:
            setattr(plan, f, None)
        plan.invoice_status = "none"
        content = f"作废发票 / 撤回开票申请：{what}" + (f"（原发票 {old}）" if old else "")
        notification_service.notify(
            db, [contract.owner_id], "invoice_voided", f"发票已作废：{what}", body.note, link
        )
    db.flush()
    activity_service.record(db, user, "contract", contract.id, "invoice", content, subject=contract)
    return contract_service.get_payment_plan(db, user, contract.id)
