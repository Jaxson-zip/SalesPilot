"""报销参与人结构化（接口契约 v3 §17）。

- 客户方联系人必须属于所关联的客户；我方同事必须是本团队成员（申请人本人自动计入，不需要选）
- headcount = 联系人数 + 同事数 + 申请人本人 + extra_guests（由 app.rules.crm_calc 计算）
- participants 文本由后端生成：「客户：王律师、陈工；我方：张晨、李薇；其他 1 人」
- 客户招待必须关联客户，且至少 1 名客户方联系人 → 否则 40001
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.scope import can_see
from app.crm.models import Contact, Expense, Opportunity, User
from app.crm.schemas.common import UserBrief
from app.crm.schemas.finance import ContactBrief, ExpenseCreate
from app.rules.crm_calc import headcount_of, participants_text


@dataclass
class Participants:
    contacts: list[Contact]
    colleagues: list[User]
    extra_guests: int
    headcount: int
    text: str


def _invalid(field: str, message: str) -> BizError:
    return BizError(
        ErrorCode.VALIDATION, message, {"errors": [{"loc": ["body", field], "msg": message}]}
    )


def _contacts(db: Session, customer_id: uuid.UUID | None, ids: list[uuid.UUID]) -> list[Contact]:
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return []
    if customer_id is None:
        raise _invalid("contact_ids", "选择客户方联系人前请先关联客户")
    stmt = select(Contact).where(Contact.id.in_(wanted), Contact.customer_id == customer_id)
    found = {c.id: c for c in db.scalars(stmt).all()}
    if len(found) != len(wanted):
        raise _invalid("contact_ids", "联系人不属于所关联的客户")
    return [found[i] for i in wanted]


def _colleagues(db: Session, user: CurrentUser, ids: list[uuid.UUID]) -> list[User]:
    wanted = [i for i in dict.fromkeys(ids) if i != user.id]  # 申请人本人自动计入
    if not wanted:
        return []
    if user.team_id is None:
        raise _invalid("colleague_ids", "我方同事必须是本团队成员")
    stmt = select(User).where(User.id.in_(wanted), User.team_id == user.team_id)
    found = {u.id: u for u in db.scalars(stmt).all()}
    if len(found) != len(wanted):
        raise _invalid("colleague_ids", "我方同事必须是本团队成员")
    return [found[i] for i in wanted]


def resolve(
    db: Session, user: CurrentUser, data: ExpenseCreate, customer_id: uuid.UUID | None
) -> Participants:
    if data.type == "entertainment":
        if customer_id is None:
            raise _invalid("customer_id", "客户招待必须关联客户")
        if not data.contact_ids:
            raise _invalid("contact_ids", "客户招待至少选择 1 名客户方联系人")
    contacts = _contacts(db, customer_id, data.contact_ids)
    colleagues = _colleagues(db, user, data.colleague_ids)
    return Participants(
        contacts=contacts,
        colleagues=colleagues,
        extra_guests=data.extra_guests,
        headcount=headcount_of(len(contacts), len(colleagues), data.extra_guests),
        text=participants_text(
            [c.name for c in contacts], user.name, [u.name for u in colleagues], data.extra_guests
        ),
    )


def briefs_of(db: Session, expense: Expense) -> tuple[list[ContactBrief], list[UserBrief]]:
    """详情用：旧数据没有结构化参与人时返回空数组。"""
    contact_ids = list(expense.contact_ids or [])
    colleague_ids = list(expense.colleague_ids or [])
    contacts: dict[uuid.UUID, Contact] = {}
    users: dict[uuid.UUID, User] = {}
    if contact_ids:
        contacts = {c.id: c for c in db.scalars(select(Contact).where(Contact.id.in_(contact_ids)))}
    if colleague_ids:
        users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(colleague_ids)))}
    return (
        [
            ContactBrief(id=c.id, name=c.name, title=c.title)
            for i in contact_ids
            if (c := contacts.get(i))
        ],
        [UserBrief(id=u.id, name=u.name) for i in colleague_ids if (u := users.get(i))],
    )


def match_names(
    db: Session, user: CurrentUser, customer_id: uuid.UUID | None, text: str
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Agent 用：在对话文本里按人名匹配客户联系人和本团队同事（匹配不到的计入其他人数）。"""
    contact_ids: list[uuid.UUID] = []
    if customer_id is not None and text:
        stmt = select(Contact).where(Contact.customer_id == customer_id)
        contact_ids = [c.id for c in db.scalars(stmt) if c.name and c.name in text]
    colleague_ids: list[uuid.UUID] = []
    if user.team_id is not None and text:
        stmt_u = select(User).where(User.team_id == user.team_id, User.id != user.id)
        colleague_ids = [u.id for u in db.scalars(stmt_u) if u.name and u.name in text]
    return contact_ids, colleague_ids


def from_conversation(
    db: Session, user: CurrentUser, data: ExpenseCreate, text: str, headcount: int | None
) -> ExpenseCreate:
    """Agent 用：按对话里的人名补全联系人 / 同事；总人数中匹配不到的计入 extra_guests。"""
    customer_id = data.customer_id
    if customer_id is None and data.opportunity_id is not None:
        opp = db.get(Opportunity, data.opportunity_id)
        customer_id = opp.customer_id if opp is not None and can_see(opp, user) else None
    contact_ids, colleague_ids = match_names(db, user, customer_id, text)
    contact_ids = list(dict.fromkeys([*data.contact_ids, *contact_ids]))
    colleague_ids = list(dict.fromkeys([*data.colleague_ids, *colleague_ids]))
    known = len(contact_ids) + len(colleague_ids) + 1
    extra = max(data.extra_guests, (headcount or 0) - known, 0)
    return data.model_copy(
        update={"contact_ids": contact_ids, "colleague_ids": colleague_ids, "extra_guests": extra}
    )
