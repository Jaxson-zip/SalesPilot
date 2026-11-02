"""开票跟踪（回款计划的每一期）：ToB 客户通常先要发票再付款。

- request：合同负责人申请开票（选专票 / 普票，可写抬头、税号等备注），通知本团队主管；
- issue：主管登记已开票（发票号码、开票日期），通知负责人；也可以不经申请直接登记；
- void：主管作废（红冲或撤回申请），必须写原因，回到未开票，通知负责人。
已开票但还没收齐的金额在回款计划和合同列表里单独提示。

每次操作记一条开票历史（invoice_events）：作废会清空期次上的发票字段，原票信息、操作人、
时间和作废原因留在历史里。操作先锁合同行，和「调整回款计划」（删除重建各期）串行，
避免调整计划用调整前读到的发票字段覆盖刚登记的发票。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner, ensure_role, ensure_same_team
from app.crm.models import Contract, InvoiceEvent, PaymentPlan
from app.crm.schemas.finance import InvoiceIn, PaymentPlanView
from app.crm.services import activity_service, contract_service, notification_service
from app.crm.services.codes import local_today

RULE_INVOICE_STATE = "invoice_bad_state"
# 动态的动作代码：前端按代码显示中文（申请开票 / 登记开票 / 作废发票 / 撤回开票申请）
ACTIVITY_ACTIONS = {"request": "invoice_request", "issue": "invoice_issue", "void": "invoice_void"}
ACTIVITY_WITHDRAW = "invoice_withdraw"
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


def _what(contract: Contract, plan: PaymentPlan) -> str:
    return f"{contract.code} {plan.name} ¥{plan.amount / 100:,.0f}"


def _link(contract: Contract) -> str:
    return f"/contracts?plan={contract.id}"


def _request(
    db: Session, user: CurrentUser, contract: Contract, plan: PaymentPlan, body: InvoiceIn
) -> str:
    what = _what(contract, plan)
    plan.invoice_status = "requested"
    plan.invoice_type = body.invoice_type or "special"
    plan.invoice_note = (body.note or "").strip() or None
    plan.invoice_requested_at = datetime.now(UTC)
    notification_service.notify(
        db,
        notification_service.team_managers(db, contract.team_id),
        "invoice_requested",
        f"开票申请：{what}",
        f"{user.name} 申请开{TYPE_NAMES[plan.invoice_type]}"
        + (f"；备注：{plan.invoice_note}" if plan.invoice_note else ""),
        _link(contract),
    )
    return f"申请开票：{what}（{TYPE_NAMES[plan.invoice_type]}）"


def _issue(db: Session, contract: Contract, plan: PaymentPlan, body: InvoiceIn) -> str:
    no = (body.invoice_no or "").strip()
    if not no:
        raise BizError(ErrorCode.VALIDATION, "请填写发票号码")
    what = _what(contract, plan)
    plan.invoice_status = "issued"
    plan.invoice_type = body.invoice_type or plan.invoice_type or "special"
    plan.invoice_no = no
    plan.invoiced_on = body.invoiced_on or local_today()
    notification_service.notify(
        db,
        [contract.owner_id],
        "invoice_issued",
        f"已开票：{what}",
        f"发票号码 {no}",
        _link(contract),
    )
    return f"已开票：{what}（{TYPE_NAMES[plan.invoice_type]} {no}）"


def _void(db: Session, contract: Contract, plan: PaymentPlan, reason: str) -> str:
    what = _what(contract, plan)
    if plan.invoice_status == "issued":
        kind = TYPE_NAMES.get(plan.invoice_type or "", "")
        old = f"原发票 {kind} {plan.invoice_no}，开票日 {plan.invoiced_on}"
        content = f"作废发票：{what}（{old}）；原因：{reason}"
    else:
        content = f"撤回开票申请：{what}；原因：{reason}"
    for f in contract_service.INVOICE_FIELDS:
        setattr(plan, f, None)
    plan.invoice_status = "none"
    notification_service.notify(
        db, [contract.owner_id], "invoice_voided", f"发票已作废：{what}", reason, _link(contract)
    )
    return content


def _event(user: CurrentUser, contract: Contract, plan: PaymentPlan, action: str) -> InvoiceEvent:
    """操作前的发票信息（作废时就是原票）：先记下来，再改期次上的字段。"""
    return InvoiceEvent(
        contract_id=contract.id,
        seq=plan.seq,
        plan_name=plan.name,
        amount=plan.amount,
        action=action,
        from_status=plan.invoice_status,
        invoice_type=plan.invoice_type,
        invoice_no=plan.invoice_no,
        invoiced_on=plan.invoiced_on,
        actor_id=user.id,
    )


def act(
    db: Session, user: CurrentUser, contract_id: uuid.UUID, seq: int, body: InvoiceIn
) -> PaymentPlanView:
    contract = db.get(Contract, contract_id, with_for_update=True)  # 和调整回款计划互斥
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
    reason = (body.note or "").strip()
    if body.action == "void" and not reason:
        raise BizError(ErrorCode.VALIDATION, "请填写作废原因（例如开票信息有误、客户要求换票）")
    event = _event(user, contract, plan, body.action)
    withdraw = body.action == "void" and plan.invoice_status == "requested"
    activity = ACTIVITY_WITHDRAW if withdraw else ACTIVITY_ACTIONS[body.action]
    if body.action == "request":
        content = _request(db, user, contract, plan, body)
    elif body.action == "issue":
        content = _issue(db, contract, plan, body)
    else:
        content = _void(db, contract, plan, reason)
    if body.action != "void":  # 申请 / 登记记操作后的票面信息
        event.invoice_type, event.invoice_no = plan.invoice_type, plan.invoice_no
        event.invoiced_on = plan.invoiced_on
    event.note = reason or None
    db.add(event)
    db.flush()
    activity_service.record(db, user, "contract", contract.id, activity, content, subject=contract)
    return contract_service.get_payment_plan(db, user, contract.id)
