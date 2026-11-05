"""报销 service（接口契约 §5）：新建草稿（制度校验存 policy_check）、列表 / 详情、提交。

提交规则：
- 票据前置条件：必备票据（rules.yaml expense.required_kinds）不全 → 42201 expense_missing_invoice
- 制度校验通过 → approved；超标 → pending_approval 并创建审批
- 拆单：同一人、同一客户、同一天已提交的客户招待合并计算人均，合计超标同样进入审批
- 同一 idempotency_key 重复新建、或对已提交的报销单再次提交 → 40901（不会重复创建审批）
"""

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common import storage
from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer, ensure_owner
from app.common.scope import View, apply_scope, ensure_visible
from app.crm.models import Customer, Expense, Opportunity
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.finance import (
    ExpenseBasics,
    ExpenseCreate,
    ExpenseDetail,
    ExpenseDetails,
    ExpenseItem,
    PolicyCheck,
)
from app.crm.services import (
    activity_service,
    approval_hints,
    approval_service,
    attachment_query,
    audit_service,
    expense_participants,
    lookup,
)
from app.crm.services.codes import next_code
from app.crm.services.expense_details import clean_details
from app.crm.services.expense_filter import ExpenseFilter, apply_filter
from app.crm.services.listing import order
from app.crm.services.quote_query import approvals_of, count
from app.rules import RuleSet, check_expense_policy, load_rules
from app.rules.loader import solo_mode

RULE_MISSING_INVOICE = "expense_missing_invoice"
RULE_NOT_EDITABLE = "expense_not_editable"
KIND_LABELS = {"invoice": "发票", "receipt": "小票", "other": "其他票据"}
# 由后端计算或单独处理的字段（客户端传入的 headcount / participants 被忽略）
CREATE_DERIVED = {
    "details",
    "customer_id",
    "headcount",
    "participants",
    "contact_ids",
    "colleague_ids",
    "extra_guests",
}


def policy_check(
    data_type: str,
    amount: int,
    headcount: int,
    rules: RuleSet,
    details: dict[str, Any] | None = None,
) -> PolicyCheck:
    result = check_expense_policy(amount, headcount, data_type, rules, details)
    return PolicyCheck(
        passed=not result.need_approval,
        per_person=result.per_person,
        limit_per_person=result.limit_per_person,
        over_amount=result.over_amount,
        rule_ref=result.rule_ref if result.limit_per_person else "",
        unit=result.unit,
    )


def _check_links(db: Session, user: CurrentUser, data: ExpenseCreate) -> uuid.UUID | None:
    """关联的客户 / 商机必须是本人负责的；只传商机时由商机带出客户。返回最终的 customer_id。"""
    customer_id = data.customer_id
    if customer_id is not None:
        ensure_owner(db.get(Customer, customer_id), user)
    if data.opportunity_id is not None:
        opp = db.get(Opportunity, data.opportunity_id)
        ensure_owner(opp, user)
        assert opp is not None
        if customer_id is not None and opp.customer_id != customer_id:
            raise BizError(ErrorCode.VALIDATION, "商机不属于该客户")
        customer_id = opp.customer_id
    return customer_id


def create_expense(
    db: Session, user: CurrentUser, data: ExpenseCreate, source: str = "manual"
) -> ExpenseDetail:
    ensure_business_writer(user)
    if data.idempotency_key:
        found = db.scalar(select(Expense).where(Expense.idempotency_key == data.idempotency_key))
        if found is not None:
            raise BizError(ErrorCode.DUPLICATE, "重复提交", {"id": str(found.id)})
    customer_id = _check_links(db, user, data)
    parts = expense_participants.resolve(db, user, data, customer_id)
    details = clean_details(data.type, data.details)  # 先校验权限和关联，再校验字段
    check = policy_check(data.type, data.amount, parts.headcount, load_rules(), details)
    expense = Expense(
        **data.model_dump(exclude=CREATE_DERIVED),
        details=details,
        customer_id=customer_id,
        headcount=parts.headcount,
        participants=parts.text,
        contact_ids=[c.id for c in parts.contacts],
        colleague_ids=[u.id for u in parts.colleagues],
        extra_guests=parts.extra_guests,
        code=next_code(db, Expense.code, "E"),
        status="draft",
        policy_check=check.model_dump(),
        owner_id=user.id,
        team_id=user.team_id,
    )
    db.add(expense)
    db.flush()
    activity_service.record(
        db, user, "expense", expense.id, "create", f"新建报销单 {expense.code}", source, expense
    )
    return get_expense(db, user, expense.id)


def _check_of(e: Expense) -> PolicyCheck | None:
    return PolicyCheck.model_validate(e.policy_check) if e.policy_check else None


def to_items(db: Session, expenses: list[Expense]) -> list[ExpenseItem]:
    customers = lookup.customers(db, (e.customer_id for e in expenses))
    owners = lookup.users(db, (e.owner_id for e in expenses))
    counts = attachment_query.counts(db, "expense", (e.id for e in expenses))
    items: list[ExpenseItem] = []
    for e in expenses:
        check = _check_of(e)
        items.append(
            ExpenseItem(
                id=e.id,
                code=e.code,
                type=e.type,  # type: ignore[arg-type]
                amount=e.amount,
                headcount=e.headcount,
                occurred_on=e.occurred_on,
                customer=lookup.pick(customers, e.customer_id),
                reason=e.reason,
                status=e.status,  # type: ignore[arg-type]
                attachment_count=counts.get(e.id, 0),
                # 超标 = 超出金额标准；「其他」类没有标准、只是要审核，不算超标
                over_limit=check is not None and not check.passed and check.over_amount > 0,
                owner=lookup.pick(owners, e.owner_id),
                created_at=e.created_at,
            )
        )
    return items


def list_expenses(
    db: Session,
    user: CurrentUser,
    view: View | None,
    page: PageParams,
    status: str | None = None,
    f: ExpenseFilter | None = None,
) -> Page[ExpenseItem]:
    stmt = apply_scope(select(Expense), Expense, user, view)
    if status:
        stmt = stmt.where(Expense.status == status)
    stmt = apply_filter(stmt, f)
    total = count(db, stmt)
    stmt = order(
        stmt,
        f.sort if f else None,
        updated=Expense.created_at,
        amount=Expense.amount,
        default=(Expense.created_at.desc(), Expense.id),
    )
    rows = list(db.scalars(stmt.offset(page.offset).limit(page.page_size)).all())
    return Page[ExpenseItem](items=to_items(db, rows), total=total)


def load_expense(
    db: Session, user: CurrentUser, expense_id: uuid.UUID, lock: bool = False
) -> Expense:
    expense = db.get(Expense, expense_id, with_for_update=lock)
    ensure_visible(expense, user)
    assert expense is not None
    return expense


# 草稿和被驳回的报销单可以修改、补票据、（重新）提交
EDITABLE_STATUSES = ("draft", "rejected")


def ensure_editable(expense: Expense, what: str = "修改") -> None:
    if expense.status not in EDITABLE_STATUSES:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报销单已提交，不能再{what}",
            {"rule": RULE_NOT_EDITABLE, "status": expense.status},
        )


def update_expense(
    db: Session, user: CurrentUser, expense_id: uuid.UUID, data: ExpenseCreate
) -> ExpenseDetail:
    """修改草稿或被驳回的报销单（整单替换），改完再提交；制度校验结果跟着重算。"""
    expense = load_owned(db, user, expense_id)
    ensure_editable(expense)
    customer_id = _check_links(db, user, data)
    parts = expense_participants.resolve(db, user, data, customer_id)
    details = clean_details(data.type, data.details)
    check = policy_check(data.type, data.amount, parts.headcount, load_rules(), details)
    for key, value in data.model_dump(exclude=CREATE_DERIVED).items():
        setattr(expense, key, value)
    expense.details = details
    expense.customer_id = customer_id
    expense.headcount = parts.headcount
    expense.participants = parts.text
    expense.contact_ids = [c.id for c in parts.contacts]
    expense.colleague_ids = [u.id for u in parts.colleagues]
    expense.extra_guests = parts.extra_guests
    expense.policy_check = check.model_dump()
    db.flush()
    content = f"修改报销单：¥{data.amount / 100:,.2f}，{data.reason}"
    activity_service.record(db, user, "expense", expense.id, "update", content, "manual", expense)
    return get_expense(db, user, expense.id)


def delete_draft(db: Session, user: CurrentUser, expense_id: uuid.UUID) -> None:
    """删除还没提交过的草稿（连同票据文件）；提交过的、被驳回的有审批记录，不能删。"""
    expense = load_owned(db, user, expense_id)
    if expense.status != "draft":
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "只有草稿可以删除；已提交或被驳回的报销单有审批记录，需要保留",
            {"rule": RULE_NOT_EDITABLE, "status": expense.status},
        )
    files = attachment_query.rows_for(db, "expense", expense.id)
    keys = [a.storage_key for a in files]
    for a in files:
        db.delete(a)
    activity_service.remove_for(db, "expense", expense.id)
    # 删除后日志里查不到单号，先记下来
    audit_service.note(f"{expense.code} · ¥{expense.amount / 100:,.2f}")
    db.delete(expense)
    db.flush()
    for key in keys:
        storage.remove(key)


def load_owned(db: Session, user: CurrentUser, expense_id: uuid.UUID) -> Expense:
    """取报销单用于修改（上传 / 删除票据、提交）：只有负责人本人可以（接口契约 §0）。"""
    expense = db.get(Expense, expense_id, with_for_update=True)
    ensure_owner(expense, user)
    assert expense is not None
    return expense


def get_expense(db: Session, user: CurrentUser, expense_id: uuid.UUID) -> ExpenseDetail:
    db.flush()
    expense = load_expense(db, user, expense_id)
    db.refresh(expense)
    opps = lookup.opportunities(db, [expense.opportunity_id])
    contacts, colleagues = expense_participants.briefs_of(db, expense)
    return ExpenseDetail(
        **to_items(db, [expense])[0].model_dump(),
        participants=expense.participants,
        contacts=contacts,
        colleagues=colleagues,
        extra_guests=expense.extra_guests or 0,
        opportunity=lookup.pick(opps, expense.opportunity_id),
        attachments=attachment_query.list_for(db, "expense", expense.id),
        policy_check=_check_of(expense),
        details=ExpenseDetails.model_validate(expense.details) if expense.details else None,
        approvals=approvals_of(db, "expense", expense.id),
    )


SPLIT_STATUSES = ("approved", "pending_approval")


def split_check(db: Session, expense: Expense, rules: RuleSet) -> tuple[PolicyCheck, str] | None:
    """同一人、同一客户、同一天的客户招待合并算人均（一顿饭拆成几张单各自不超标）。

    人数取几张单里最多的（同一顿饭的参与人），合计超标时返回合并后的校验结果和原因。
    """
    if expense.type != "entertainment" or expense.customer_id is None:
        return None
    others = list(
        db.scalars(
            select(Expense).where(
                Expense.id != expense.id,
                Expense.owner_id == expense.owner_id,
                Expense.customer_id == expense.customer_id,
                Expense.occurred_on == expense.occurred_on,
                Expense.type == "entertainment",
                Expense.status.in_(SPLIT_STATUSES),
            )
        )
    )
    if not others:
        return None
    total = expense.amount + sum(e.amount for e in others)
    headcount = max([expense.headcount, *(e.headcount for e in others)])
    merged = policy_check("entertainment", total, headcount, rules)
    if merged.passed:
        return None
    codes = "、".join(e.code for e in others)
    reason = (
        f"同一天同一客户已有招待报销 {codes}，合计 ¥{total / 100:,.0f}、"
        f"人均 ¥{merged.per_person / 100:.0f} 超出标准 ¥{merged.limit_per_person / 100:.0f}/人，"
        "疑似拆单，需主管审批"
    )
    return merged, reason


def missing_kinds(db: Session, expense: Expense, rules: RuleSet) -> list[str]:
    have = {a.kind for a in attachment_query.rows_for(db, "expense", expense.id)}
    return [k for k in rules.expense.kinds_for(expense.type) if k not in have]


def ensure_complete(expense: Expense) -> None:
    """提交（可能自动通过）前再把整单校验一遍：保存时的校验之前没有、或数据是别处写进来的，
    都在这里拦下，不让空事由、未来日期的报销单自动通过。"""
    try:
        ExpenseBasics(reason=expense.reason or "", occurred_on=expense.occurred_on)
        clean_details(expense.type, ExpenseDetails.model_validate(expense.details or {}))
    except ValidationError as e:
        msg = str(e.errors()[0]["msg"]).removeprefix("Value error, ")
        raise BizError(ErrorCode.VALIDATION, msg, {"errors": [{"msg": msg}]}) from e


def submit_expense(
    db: Session, user: CurrentUser, expense_id: uuid.UUID, source: str = "manual"
) -> ExpenseDetail:
    expense = load_owned(db, user, expense_id)
    if expense.status not in EDITABLE_STATUSES:
        raise BizError(
            ErrorCode.DUPLICATE, "报销单已提交，请勿重复提交", {"status": expense.status}
        )
    again = expense.status == "rejected"
    ensure_complete(expense)
    rules = load_rules()
    missing = missing_kinds(db, expense, rules)
    if missing:
        names = "、".join(KIND_LABELS.get(k, k) for k in missing)
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"请先上传{names}",
            {"rule": RULE_MISSING_INVOICE, "missing": missing},
        )
    check = policy_check(expense.type, expense.amount, expense.headcount, rules, expense.details)
    expense.policy_check = check.model_dump()
    reason = check_expense_policy(
        expense.amount, expense.headcount, expense.type, rules, expense.details
    ).reason
    if check.passed and (split := split_check(db, expense, rules)):
        check, reason = split
        expense.policy_check = check.model_dump()
    if check.passed:
        expense.status = "approved"
        content = f"{'重新' if again else ''}提交报销单，制度校验通过：{reason}"
    elif solo_mode():
        expense.status = "approved"  # 个人模式：没有别人可以审批，超标原因照常记下
        content = f"{'重新' if again else ''}提交报销单，个人模式免审批（提醒：{reason}）"
    else:
        expense.status = "pending_approval"
        hint = approval_hints.expense_hint(
            db, expense.customer_id, expense.owner_id, check.over_amount
        )
        approval_service.create_approval(db, "expense", expense, reason, hint)
        content = f"{'重新' if again else ''}提交报销单，超标进入主管审批：{reason}"
    db.flush()
    activity_service.record(db, user, "expense", expense.id, "submit", content, source, expense)
    return get_expense(db, user, expense.id)


def create_and_submit(
    db: Session, user: CurrentUser, data: ExpenseCreate, source: str = "agent"
) -> ExpenseDetail:
    """Agent 用：新建草稿；票据已齐时直接提交，否则保留草稿等销售上传票据。"""
    detail = create_expense(db, user, data, source)
    expense = load_expense(db, user, detail.id)
    if missing_kinds(db, expense, load_rules()):
        return detail
    return submit_expense(db, user, detail.id, source)
