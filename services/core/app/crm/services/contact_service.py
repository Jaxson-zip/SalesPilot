"""联系人 service（B7 联系人角色、U11 联系人增删改）。

联系人跟着客户走：能看到客户就能看到联系人；只有客户负责人能增删改（ensure_owner）。
is_decision_maker 由 role 派生，保留给旧接口和报销参与人使用。
"""

import uuid

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.common.scope import ensure_visible
from app.crm.models import Contact, Customer
from app.crm.schemas.common import Page
from app.crm.schemas.dashboard import CONTACT_ROLE_LABELS, ContactIn, ContactItem, ContactUpdate
from app.crm.services import activity_service

# 列表排序：决策人、影响者、技术把关、采购财务、使用者、未标注
_ROLE_ORDER = {role: i for i, role in enumerate(CONTACT_ROLE_LABELS)}


def to_item(c: Contact) -> ContactItem:
    return ContactItem(
        id=c.id,
        name=c.name,
        title=c.title,
        phone=c.phone,
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


def delete_contact(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, contact_id: uuid.UUID
) -> None:
    customer, contact = _owned_contact(db, user, customer_id, contact_id)
    name = contact.name
    db.delete(contact)
    db.flush()
    activity_service.record(
        db, user, "customer", customer.id, "contact_removed", name,
        subject=customer,
    )  # fmt: skip
