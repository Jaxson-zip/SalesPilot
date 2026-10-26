"""转移客户负责人（接口契约 v3 §16）：仅主管，客户和目标都必须属于本团队。

一起转移：客户、联系人、跟进记录、未结束的商机、未完成的任务、未成交的报价（及其待审批记录），
以及这些对象上的动态（动态可见范围跟随负责人）。已成交的合同、提成和报销单不转移。
"""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import RULE_NOT_TEAM, ensure_role, ensure_same_team, forbidden
from app.crm.models import (
    Activity,
    Approval,
    Contact,
    Customer,
    Followup,
    Opportunity,
    Quote,
    Task,
    User,
)
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.schemas.task import CustomerTransfer, TransferResult
from app.crm.services import activity_service, notification_service

OPEN_QUOTE_STATUSES = ("draft", "pending_approval", "approved", "sent")
ASSIGNABLE_ROLES = (Role.SALES.value, Role.MANAGER.value)


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
    return target


def _ids(db: Session, stmt: Any) -> list[uuid.UUID]:
    return list(db.scalars(stmt).all())


def _move(db: Session, customer: Customer, owner: dict[str, Any]) -> dict[str, int]:
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
        stats = _move(db, customer, owner)
        _notify_and_log(
            db, user, customer, old.name if old else "公海", target, stats["opportunities"]
        )
        totals["transferred"] += 1
        for key, value in stats.items():
            totals[key] += value
    return TransferResult(**totals)
