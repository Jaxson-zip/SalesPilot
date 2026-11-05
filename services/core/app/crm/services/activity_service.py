"""动态记录：挂在客户 / 商机 / 报价 / 合同 / 报销上。

owner_id / team_id 跟随被操作对象（subject）的负责人，因此动态的可见范围与业务数据一致：
主管改了销售的商机阶段，销售本人也能在动态里看到。
"""

import uuid
from typing import Any

from sqlalchemy import ColumnElement, and_, delete, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.scope import ScopedModel, View, apply_scope
from app.crm.models import Activity, Contract, Customer, Expense, Opportunity, Quote, User
from app.crm.schemas.common import ActivityOut, UserBrief

MAX_LIMIT = 100


def record(
    db: Session,
    user: CurrentUser,
    subject_type: str,
    subject_id: uuid.UUID,
    action: str,
    content: str | None = None,
    source: str = "manual",
    subject: ScopedModel | None = None,
) -> Activity:
    if subject is not None and subject.owner_id is not None:
        owner_id, team_id = subject.owner_id, subject.team_id
    else:
        owner_id, team_id = user.id, user.team_id
    activity = Activity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=None if source == "agent" else user.id,
        source=source,
        action=action,
        content=content,
        owner_id=owner_id,
        team_id=team_id,
    )
    db.add(activity)
    db.flush()
    return activity


def remove_for(db: Session, subject_type: str, subject_id: uuid.UUID) -> None:
    """对象被删除时清掉它的动态，免得工作台上留着点不开的记录（删除本身记在操作日志里）。"""
    db.execute(
        delete(Activity).where(
            Activity.subject_type == subject_type, Activity.subject_id == subject_id
        )
    )


def record_system(
    db: Session,
    subject_type: str,
    subject_id: uuid.UUID,
    action: str,
    content: str | None,
    team_id: uuid.UUID | None,
    owner_id: uuid.UUID | None = None,
) -> Activity:
    """定时任务等系统操作留下的动态：没有操作人，来源记为 system。"""
    activity = Activity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=None,
        source="system",
        action=action,
        content=content,
        owner_id=owner_id,
        team_id=team_id,
    )
    db.add(activity)
    db.flush()
    return activity


def _to_out(row: Any) -> ActivityOut:
    a: Activity = row.Activity
    actor = UserBrief(id=a.actor_id, name=row.actor_name) if a.actor_id and row.actor_name else None
    return ActivityOut(
        id=a.id,
        subject_type=a.subject_type,
        subject_id=a.subject_id,
        actor=actor,
        source="agent" if a.source == "agent" else "manual",
        action=a.action,
        content=a.content,
        created_at=a.created_at,
    )


# 客户时间线里带上的商机 / 报价 / 合同里程碑；改字段、提交审批等内部步骤不显示
CUSTOMER_MILESTONES: dict[str, tuple[Any, tuple[str, ...]]] = {
    "opportunity": (Opportunity, ("create", "stage_changed")),
    "quote": (Quote, ("send", "viewed", "accept", "reject")),
    "contract": (
        Contract,
        ("payment", "payment_reverse", "invoice_request", "invoice_issue", "invoice_void"),
    ),
}


def _customer_related(customer_id: uuid.UUID) -> ColumnElement[bool]:
    """客户本身的动态 + 这个客户名下商机、报价、合同的里程碑。

    回归：客户时间线原来只查挂在客户上的动态，报价发出、客户接受、回款、开票都看不到。
    """
    conds = [and_(Activity.subject_type == "customer", Activity.subject_id == customer_id)]
    for subject_type, (model, actions) in CUSTOMER_MILESTONES.items():
        ids = select(model.id).where(model.customer_id == customer_id)
        conds.append(
            and_(
                Activity.subject_type == subject_type,
                Activity.action.in_(actions),
                Activity.subject_id.in_(ids),
            )
        )
    return or_(*conds)


def list_activities(
    db: Session,
    user: CurrentUser,
    view: View | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    limit: int = 20,
    related: bool = False,
) -> list[ActivityOut]:
    """动态流：按数据范围过滤，最新的在前；related 只对客户有效，带上名下商机等的里程碑。"""
    stmt = select(Activity, User.name.label("actor_name")).outerjoin(
        User, User.id == Activity.actor_id
    )
    if related and subject_type == "customer" and subject_id:
        stmt = stmt.where(_customer_related(subject_id))
    else:
        if subject_type:
            stmt = stmt.where(Activity.subject_type == subject_type)
        if subject_id:
            stmt = stmt.where(Activity.subject_id == subject_id)
    stmt = apply_scope(stmt, Activity, user, view)
    stmt = stmt.order_by(Activity.created_at.desc(), Activity.id).limit(min(limit, MAX_LIMIT))
    return _with_names(db, [_to_out(r) for r in db.execute(stmt).all()])


# 动态对象 → (模型, 显示的字段)：客户 / 商机显示名称，单据显示编号
_NAMED: dict[str, tuple[Any, Any]] = {
    "customer": (Customer, Customer.name),
    "opportunity": (Opportunity, Opportunity.name),
    "quote": (Quote, Quote.code),
    "contract": (Contract, Contract.code),
    "expense": (Expense, Expense.code),
}


def _with_names(db: Session, rows: list[ActivityOut]) -> list[ActivityOut]:
    """按对象类型各查一次名称（工作台动态流用，详情页的时间线不需要）。"""
    for subject_type, (model, column) in _NAMED.items():
        ids = {r.subject_id for r in rows if r.subject_type == subject_type}
        if not ids:
            continue
        names = {k: v for k, v in db.execute(select(model.id, column).where(model.id.in_(ids)))}
        for r in rows:
            if r.subject_type == subject_type:
                r.subject_name = names.get(r.subject_id)
    return rows


def list_for_subject(db: Session, subject_id: uuid.UUID, limit: int = 50) -> list[ActivityOut]:
    """详情页用：调用方已校验过 subject 的可见性，这里不再按范围过滤。"""
    stmt = (
        select(Activity, User.name.label("actor_name"))
        .outerjoin(User, User.id == Activity.actor_id)
        .where(Activity.subject_id == subject_id)
        .order_by(Activity.created_at.desc(), Activity.id)
        .limit(limit)
    )
    return [_to_out(r) for r in db.execute(stmt).all()]
