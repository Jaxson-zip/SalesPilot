"""转移客户负责人（接口契约 v3 §16）：仅主管，客户和目标都必须属于本团队。

一起转移：客户、联系人、跟进记录、未结束的商机、未完成的任务、未成交的报价（及其待审批记录），
以及这些对象上的动态（动态可见范围跟随负责人）。已成交的合同、提成和报销单不转移。

按人一键交接（离职 / 调岗）：在上面基础上一次转走这个人名下的全部客户，回款中的合同和回款计划
也交给接手人跟进回款、申请开票；提成仍归原负责人（提成按人记录，不跟合同负责人走）。
"""

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import RULE_NOT_TEAM, ensure_role, ensure_same_team, forbidden
from app.crm.models import (
    Activity,
    Approval,
    Contact,
    Contract,
    Customer,
    Followup,
    Opportunity,
    PaymentPlan,
    Quote,
    Task,
    User,
)
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.schemas.task import CustomerTransfer, HandoverIn, HandoverResult, TransferResult
from app.crm.services import activity_service, notification_service

OPEN_QUOTE_STATUSES = ("draft", "pending_approval", "approved", "sent")
ASSIGNABLE_ROLES = (Role.SALES.value, Role.MANAGER.value)
RULE_HANDOVER_SELF = "handover_same_user"


def _target(db: Session, user: CurrentUser, user_id: uuid.UUID) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise BizError(ErrorCode.NOT_FOUND, "目标用户不存在")
    if (
        user.team_id is None
        or target.team_id != user.team_id
        or target.role not in ASSIGNABLE_ROLES
    ):
        raise forbidden("只能转给本团队的销售或主管", RULE_NOT_TEAM)
    if not target.active:
        raise BizError(
            ErrorCode.RULE_VIOLATION, f"{target.name} 的账号已停用，不能接手客户",
            {"rule": "user_inactive"},
        )  # fmt: skip
    return target


def _ids(db: Session, stmt: Any) -> list[uuid.UUID]:
    return list(db.scalars(stmt).all())


def move_customer(db: Session, customer: Customer, owner: dict[str, Any]) -> dict[str, int]:
    """把客户及其进行中的业务数据转给新负责人，返回各类转移数量。"""
    cid = customer.id
    opp_ids = _ids(
        db,
        select(Opportunity.id).where(
            Opportunity.customer_id == cid, Opportunity.stage.not_in(FINAL_STAGES)
        ),
    )
    quote_ids = _ids(
        db, select(Quote.id).where(Quote.customer_id == cid, Quote.status.in_(OPEN_QUOTE_STATUSES))
    )
    task_ids = _ids(db, select(Task.id).where(Task.customer_id == cid, Task.done.is_(False)))
    customer.owner_id, customer.team_id = owner["owner_id"], owner["team_id"]
    moves: list[tuple[Any, Any]] = [
        (Contact, Contact.customer_id == cid),
        (Followup, Followup.customer_id == cid),
        (Opportunity, Opportunity.id.in_(opp_ids)),
        (Quote, Quote.id.in_(quote_ids)),
        (Task, Task.id.in_(task_ids)),
        (Approval, Approval.target_id.in_(quote_ids) & (Approval.status == "pending")),
        (Activity, Activity.subject_id.in_([cid, *opp_ids, *quote_ids])),
    ]
    for model, where in moves:
        db.execute(update(model).where(where).values(**owner))
    db.flush()
    return {"opportunities": len(opp_ids), "tasks": len(task_ids), "quotes": len(quote_ids)}


def _notify_and_log(
    db: Session, user: CurrentUser, customer: Customer, old_name: str, target: User, moved: int
) -> None:
    activity_service.record(
        db, user, "customer", customer.id, "transfer",
        f"负责人：{old_name} → {target.name}", subject=customer,
    )  # fmt: skip
    notification_service.notify(
        db,
        [target.id],
        "customer_assigned",
        f"客户转给你负责：{customer.name}",
        f"{user.name} 将客户转给你，含 {moved} 个进行中的商机",
        notification_service.subject_link("customer", customer.id),
    )


def transfer_customers(db: Session, user: CurrentUser, data: CustomerTransfer) -> TransferResult:
    ensure_role(user, Role.MANAGER, "仅销售主管可以转移客户负责人")
    target = _target(db, user, data.to_user_id)
    customers: list[Customer] = []
    for cid in dict.fromkeys(data.customer_ids):  # 去重并保持顺序
        customer = db.get(Customer, cid, with_for_update=True)
        ensure_same_team(customer, user)  # 看不到 40401；不是本团队 40301 not_team
        assert customer is not None
        customers.append(customer)
    owner = {"owner_id": target.id, "team_id": target.team_id}
    totals = {"transferred": 0, "opportunities": 0, "tasks": 0, "quotes": 0}
    for customer in customers:
        if customer.owner_id == target.id:
            continue
        old = db.get(User, customer.owner_id) if customer.owner_id else None
        stats = move_customer(db, customer, owner)
        _notify_and_log(
            db, user, customer, old.name if old else "公海", target, stats["opportunities"]
        )
        totals["transferred"] += 1
        for key, value in stats.items():
            totals[key] += value
    return TransferResult(**totals)


# ---------- 按人一键交接 ----------


def _source(db: Session, user: CurrentUser, user_id: uuid.UUID) -> User:
    """交接人：本团队的销售或主管（可以是已停用的账号）。"""
    ensure_role(user, Role.MANAGER, "仅销售主管可以交接客户")
    source = db.get(User, user_id)
    if source is None:
        raise BizError(ErrorCode.NOT_FOUND, "交接人不存在")
    if user.team_id is None or source.team_id != user.team_id:
        raise forbidden("只能交接本团队成员的客户", RULE_NOT_TEAM)
    return source


def _count(db: Session, model: Any, *where: Any) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def preview_handover(db: Session, user: CurrentUser, from_id: uuid.UUID) -> HandoverResult:
    """交接前预览：这个人名下有多少客户和进行中的业务（不修改数据）。"""
    source = _source(db, user, from_id)
    sid = source.id
    return HandoverResult(
        customers=_count(db, Customer, Customer.owner_id == sid, Customer.team_id == user.team_id),
        opportunities=_count(
            db, Opportunity, Opportunity.owner_id == sid, Opportunity.stage.not_in(FINAL_STAGES)
        ),
        tasks=_count(db, Task, Task.owner_id == sid, Task.done.is_(False)),
        quotes=_count(db, Quote, Quote.owner_id == sid, Quote.status.in_(OPEN_QUOTE_STATUSES)),
        contracts=_count(db, Contract, Contract.owner_id == sid, Contract.status == "active"),
    )


def _move_contracts(db: Session, source_id: uuid.UUID, owner: dict[str, Any]) -> int:
    """回款中的合同连同回款计划、合同动态交给接手人；提成记录不动。"""
    ids = _ids(
        db, select(Contract.id).where(Contract.owner_id == source_id, Contract.status == "active")
    )
    if ids:
        db.execute(update(Contract).where(Contract.id.in_(ids)).values(**owner))
        db.execute(update(PaymentPlan).where(PaymentPlan.contract_id.in_(ids)).values(**owner))
        db.execute(update(Activity).where(Activity.subject_id.in_(ids)).values(**owner))
    return len(ids)


def handover(db: Session, user: CurrentUser, data: HandoverIn) -> HandoverResult:
    """把 from_user 名下全部客户、进行中的业务和回款中的合同一次转给 to_user。"""
    source = _source(db, user, data.from_user_id)
    target = _target(db, user, data.to_user_id)
    if source.id == target.id:
        raise BizError(
            ErrorCode.RULE_VIOLATION, "交接人和接手人不能是同一个人", {"rule": RULE_HANDOVER_SELF}
        )
    owner = {"owner_id": target.id, "team_id": target.team_id}
    customers = db.scalars(
        select(Customer)
        .where(Customer.owner_id == source.id, Customer.team_id == user.team_id)
        .order_by(Customer.created_at)
        .with_for_update()
    ).all()
    totals = {"opportunities": 0, "tasks": 0, "quotes": 0}
    for customer in customers:
        for key, value in move_customer(db, customer, owner).items():
            totals[key] += value
        activity_service.record(
            db, user, "customer", customer.id, "transfer",
            f"交接：{source.name} → {target.name}", subject=customer,
        )  # fmt: skip
    # 客户之外还留在原负责人名下的未完成任务也一起交接
    stray = update(Task).where(Task.owner_id == source.id, Task.done.is_(False)).values(**owner)
    totals["tasks"] += db.execute(stray).rowcount or 0  # type: ignore[attr-defined]
    contracts = _move_contracts(db, source.id, owner)
    db.flush()
    result = HandoverResult(customers=len(customers), contracts=contracts, **totals)
    if result.customers or result.contracts or result.tasks:
        notification_service.notify(
            db,
            [target.id],
            "customer_handover",
            f"{source.name} 的客户交接给你",
            f"{user.name} 将 {source.name} 名下 {result.customers} 个客户、"
            f"{result.opportunities} 个进行中的商机、{result.contracts} 份回款中的合同交接给你",
            "/customers",
        )
    return result
