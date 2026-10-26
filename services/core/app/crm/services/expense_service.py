"""报销 service（接口契约 §5）：新建草稿（制度校验存 policy_check）、列表 / 详情、提交。

提交规则：
- 票据前置条件：必备票据（rules.yaml expense.required_kinds）不全 → 42201 expense_missing_invoice
- 制度校验通过 → approved；超标 → pending_approval 并创建审批
- 同一 idempotency_key 重复新建、或对已提交的报销单再次提交 → 40901（不会重复创建审批）
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer, ensure_owner
from app.common.scope import View, apply_scope, ensure_visible
from app.crm.models import Customer, Expense, Opportunity
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.finance import (
    ExpenseCreate,
    ExpenseDetail,
    ExpenseDetails,
    ExpenseItem,
    PolicyCheck,
)
from app.crm.services import (
    activity_service,
    approval_service,
    attachment_query,
    expense_participants,
    lookup,
)
from app.crm.services.codes import next_code
from app.crm.services.expense_details import clean_details
from app.crm.services.quote_query import count
from app.rules import RuleSet, check_expense_policy, load_rules

RULE_MISSING_INVOICE = "expense_missing_invoice"
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
                over_limit=check is not None and not check.passed,
                owner=lookup.pick(owners, e.owner_id),
                created_at=e.created_at,
            )
        )
    return items


def list_expenses(
    db: Session, user: CurrentUser, view: View | None, page: PageParams, status: str | None = None
) -> Page[ExpenseItem]:
    stmt = apply_scope(select(Expense), Expense, user, view)
    if status:
        stmt = stmt.where(Expense.status == status)
    total = count(db, stmt)
    stmt = stmt.order_by(Expense.created_at.desc(), Expense.id)
    rows = list(db.scalars(stmt.offset(page.offset).limit(page.page_size)).all())
    return Page[ExpenseItem](items=to_items(db, rows), total=total)


def load_expense(
    db: Session, user: CurrentUser, expense_id: uuid.UUID, lock: bool = False
) -> Expense:
    expense = db.get(Expense, expense_id, with_for_update=lock)
    ensure_visible(expense, user)
    assert expense is not None
    return expense


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
    )


def missing_kinds(db: Session, expense: Expense, rules: RuleSet) -> list[str]:
    have = {a.kind for a in attachment_query.rows_for(db, "expense", expense.id)}
    return [k for k in rules.expense.kinds_for(expense.type) if k not in have]


def _suggestion(check: PolicyCheck) -> str:
    return (
        f"超出标准 ¥{check.over_amount / 100:,.0f}。建议核实参与人数与招待事由；"
        "属于重点客户关键节点可通过，否则超出部分由个人承担。"
    )


def submit_expense(
    db: Session, user: CurrentUser, expense_id: uuid.UUID, source: str = "manual"
) -> ExpenseDetail:
    expense = load_owned(db, user, expense_id)
    if expense.status != "draft":
        raise BizError(
            ErrorCode.DUPLICATE, "报销单已提交，请勿重复提交", {"status": expense.status}
        )
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
    if check.passed:
        expense.status = "approved"
        content = f"提交报销单，制度校验通过：{reason}"
    else:
        expense.status = "pending_approval"
        approval_service.create_approval(db, "expense", expense, reason, _suggestion(check))
        content = f"提交报销单，超标进入主管审批：{reason}"
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
