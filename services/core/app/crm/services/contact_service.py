"""联系人 service（B7 联系人角色、U11 联系人增删改）。

联系人跟着客户走：能看到客户就能看到联系人；只有客户负责人能增删改（ensure_owner）。
is_decision_maker 由 role 派生，保留给旧接口和报销参与人使用。
"""

import uuid

from sqlalchemy import any_, case, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.common.scope import ensure_visible
from app.crm.models import Contact, Customer, Expense
from app.crm.schemas.common import Page
from app.crm.schemas.dashboard import (
    CONTACT_ROLE_LABELS,
    ContactIn,
    ContactItem,
    ContactUpdate,
    PhoneOut,
)
from app.crm.services import activity_service, audit_service
from app.rules import load_rules

# 列表排序：决策人、影响者、技术把关、采购财务、使用者、未标注
_ROLE_ORDER = {role: i for i, role in enumerate(CONTACT_ROLE_LABELS)}


def mask_phone(phone: str | None) -> str | None:
    """139****2222：保留前 3 位和后 4 位；太短的号码只留最后 2 位。"""
    if not phone:
        return phone
    digits = phone.strip()
    if len(digits) >= 8:
        return f"{digits[:3]}****{digits[-4:]}"
    return "*" * max(len(digits) - 2, 1) + digits[-2:]


def is_masked(phone: str | None) -> bool:
    return bool(phone) and "*" in str(phone)


def to_item(c: Contact) -> ContactItem:
    return ContactItem(
        id=c.id,
        name=c.name,
        title=c.title,
        phone=mask_phone(c.phone),
        has_phone=bool(c.phone),
        is_decision_maker=c.is_decision_maker,
        role=c.role,  # type: ignore[arg-type]
    )


def describe(c: Contact) -> str:
    """「王律师（管理合伙人 · 决策人）」：动态和 Agent 摘要用。"""
    extra = [x for x in (c.title, CONTACT_ROLE_LABELS.get(c.role or "")) if x]
    return f"{c.name}（{' · '.join(extra)}）" if extra else c.name


def list_contacts(db: Session, user: CurrentUser, customer_id: uuid.UUID) -> Page[ContactItem]:
    """客户联系人：先校验客户可见（看不到 → 40401），按角色重要程度排序。"""
    ensure_visible(db.get(Customer, customer_id), user)
    order = case(_ROLE_ORDER, value=Contact.role, else_=len(_ROLE_ORDER))
    stmt = (
        select(Contact)
        .where(Contact.customer_id == customer_id)
        .order_by(order, Contact.created_at, Contact.id)
    )
    items = [to_item(c) for c in db.scalars(stmt)]
    return Page[ContactItem](items=items, total=len(items))


def create_contact(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, data: ContactIn
) -> ContactItem:
    customer = db.get(Customer, customer_id)
    ensure_owner(customer, user)
    assert customer is not None
    contact = Contact(
        customer_id=customer.id,
        name=data.name.strip(),
        title=data.title,
        phone=data.phone,
        role=data.role,
        is_decision_maker=data.role == "decision_maker",
        owner_id=customer.owner_id,
        team_id=customer.team_id,
    )
    db.add(contact)
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, "contact_added",
        describe(contact), subject=customer,
    )  # fmt: skip
    return to_item(contact)


def _owned_contact(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, contact_id: uuid.UUID
) -> tuple[Customer, Contact]:
    customer = db.get(Customer, customer_id)
    ensure_owner(customer, user)
    contact = db.get(Contact, contact_id)
    if contact is None or contact.customer_id != customer_id:
        raise BizError(ErrorCode.NOT_FOUND)
    assert customer is not None
    return customer, contact


def update_contact(
    db: Session,
    user: CurrentUser,
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    data: ContactUpdate,
) -> ContactItem:
    customer, contact = _owned_contact(db, user, customer_id, contact_id)
    changes = data.model_dump(exclude_unset=True)
    if is_masked(changes.get("phone")):
        changes.pop("phone")  # 表单原样提交了脱敏号码：不修改电话
    for key, value in changes.items():
        setattr(contact, key, value.strip() if key == "name" and value else value)
    if "role" in changes:
        contact.is_decision_maker = contact.role == "decision_maker"
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, "contact_updated",
        describe(contact), subject=customer,
    )  # fmt: skip
    return to_item(contact)


RULE_CONTACT_IN_EXPENSE = "contact_in_open_expense"
OPEN_EXPENSES = ("draft", "pending_approval", "rejected")


def _ensure_not_in_open_expense(db: Session, contact: Contact) -> None:
    """还能修改的报销单（草稿 / 待审批 / 被驳回）里用到的联系人不能删。

    删了以后重新编辑报销单，这位客户方参与人会消失，人数和人均金额跟着变，可能变成超标。
    已审批的报销单另存了参与人文字，不受影响。
    """
    codes = db.scalars(
        select(Expense.code).where(
            contact.id == any_(Expense.contact_ids), Expense.status.in_(OPEN_EXPENSES)
        )
    ).all()
    if codes:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"{contact.name} 是报销单 {'、'.join(codes[:3])} 的客户方参与人，"
            "这些报销单处理完之前不能删除",
            {"rule": RULE_CONTACT_IN_EXPENSE, "expenses": list(codes)},
        )


def delete_contact(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, contact_id: uuid.UUID
) -> None:
    customer, contact = _owned_contact(db, user, customer_id, contact_id)
    _ensure_not_in_open_expense(db, contact)
    name = contact.name
    db.delete(contact)
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, "contact_removed", name,
        subject=customer,
    )  # fmt: skip


def reveal_phone(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, contact_id: uuid.UUID, ip: str | None
) -> PhoneOut:
    """查看完整电话：能看到客户的人都可以查看，每次记操作日志，每人每天限次（rules.privacy）。"""
    ensure_visible(db.get(Customer, customer_id), user)
    contact = db.get(Contact, contact_id)
    if contact is None or contact.customer_id != customer_id or not contact.phone:
        raise BizError(ErrorCode.NOT_FOUND)
    action, label = audit_service.PHONE_REVEAL
    limit = load_rules().privacy.phone_reveal_daily_limit
    used = audit_service.count_today(db, user, action)
    entry = audit_service.AuditEntry(
        action=action, label=label, target_id=str(contact.id), detail=contact.name, ip=ip
    )
    if used >= limit:
        msg = f"今天查看电话已达上限（{limit} 次），如需更多请联系管理员"
        audit_service.record(
            user, entry.model_copy(update={"ok": False, "status": 429, "detail": msg})
        )
        raise BizError(ErrorCode.RATE_LIMITED, msg)
    audit_service.write(db, user, entry)
    return PhoneOut(phone=contact.phone, remaining=limit - used - 1)
