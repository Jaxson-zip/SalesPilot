"""审批 service（接口契约 §6）：创建审批、本团队审批列表、通过 / 驳回并联动目标对象状态。

只有 manager 能查看和处理审批（其他角色 40301）；主管只能处理本团队的审批（看不到 → 40401）。
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_role, ensure_same_team
from app.common.scope import View, apply_scope
from app.crm.models import Approval, Expense, Quote, User
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.finance import EXPENSE_TYPE_LABELS, ApprovalItem, ApprovalTarget
from app.crm.services import (
    activity_service,
    attachment_query,
    lookup,
    notification_service,
    quote_query,
    wecom_service,
)
from app.packs.base import TIER_NAMES

RULE_ALREADY_DECIDED = "approval_already_decided"
DONE_STATUSES = ("approved", "rejected")
# 审批结果 → 目标对象的新状态（报价驳回退回草稿，可修改后重新提交）
TARGET_STATUS: dict[tuple[str, str], str] = {
    ("quote", "approve"): "approved",
    ("quote", "reject"): "draft",
    ("expense", "approve"): "approved",
    ("expense", "reject"): "rejected",
}


def create_approval(
    db: Session,
    target_type: str,
    target: Quote | Expense,
    reason: str,
    ai_suggestion: str | None = None,
) -> Approval:
    """审批归属于目标对象的负责人与团队，主管按团队范围看到。"""
    approval = Approval(
        target_type=target_type,
        target_id=target.id,
        reason=reason,
        ai_suggestion=ai_suggestion,
        status="pending",
        owner_id=target.owner_id,
        team_id=target.team_id,
    )
    db.add(approval)
    db.flush()
    kind = "报价单" if target_type == "quote" else "报销单"
    notification_service.notify(
        db,
        notification_service.team_managers(db, target.team_id),
        "approval_pending",
        f"待审批：{kind} {target.code}",
        reason,
        "/approvals",
    )
    owner = db.get(User, target.owner_id) if target.owner_id else None
    amount = target.total_price if isinstance(target, Quote) else target.amount
    wecom_service.queue(
        db,
        "approval_pending",
        f"待审批：{kind} {target.code}",
        f"**待审批：{kind} {target.code}**\n"
        f"> 提交人：{owner.name if owner else '—'}\n"
        f'> 金额：<font color="warning">¥{amount / 100:,.0f}</font>\n'
        f"> 原因：{reason}\n\n{wecom_service.link('/approvals', '去审批')}",
    )
    return approval


def require_manager(user: CurrentUser) -> None:
    ensure_role(user, Role.MANAGER, "仅销售主管可以处理审批")


def _targets(db: Session, approvals: list[Approval]) -> dict[uuid.UUID, Quote | Expense]:
    quote_ids = [a.target_id for a in approvals if a.target_type == "quote"]
    expense_ids = [a.target_id for a in approvals if a.target_type == "expense"]
    found: dict[uuid.UUID, Quote | Expense] = {}
    if quote_ids:
        found.update({q.id: q for q in db.scalars(select(Quote).where(Quote.id.in_(quote_ids)))})
    if expense_ids:
        stmt = select(Expense).where(Expense.id.in_(expense_ids))
        found.update({e.id: e for e in db.scalars(stmt)})
    return found


def _title(target: Quote | Expense, customers: dict[uuid.UUID, Any]) -> str:
    customer = lookup.pick(customers, target.customer_id)
    name = customer.name if customer else None
    if isinstance(target, Quote):
        tier = TIER_NAMES.get(target.tier, target.tier)
        return f"{name} · {tier}报价" if name else f"{tier}报价"
    label = EXPENSE_TYPE_LABELS.get(target.type, target.type)
    return f"{label} · {name}" if name else label


def to_items(db: Session, approvals: list[Approval]) -> list[ApprovalItem]:
    targets = _targets(db, approvals)
    owners = lookup.users(db, (t.owner_id for t in targets.values()))
    customers = lookup.customers(db, (t.customer_id for t in targets.values()))
    items: list[ApprovalItem] = []
    for a in approvals:
        t = targets.get(a.target_id)
        if t is None:
            continue
        if isinstance(t, Quote):
            extra: dict[str, Any] = {"amount": t.total_price, "margin_rate": t.margin_rate}
        else:
            over = (t.policy_check or {}).get("over_amount")
            extra = {
                "amount": t.amount,
                "over_amount": over if isinstance(over, int) else None,
                "occurred_on": t.occurred_on,
            }
        target = ApprovalTarget(
            id=t.id,
            code=t.code,
            title=_title(t, customers),
            owner=lookup.pick(owners, t.owner_id),
            **extra,
        )
        items.append(
            ApprovalItem(
                id=a.id,
                target_type=a.target_type,  # type: ignore[arg-type]
                target=target,
                reason=a.reason,
                ai_suggestion=a.ai_suggestion,
                status=a.status,  # type: ignore[arg-type]
                attachments=attachment_query.list_for(db, a.target_type, t.id),
                comment=a.comment,
                decided_at=a.decided_at,
                created_at=a.created_at,
            )
        )
    return items


def list_approvals(
    db: Session, user: CurrentUser, status: str | None, page: PageParams
) -> Page[ApprovalItem]:
    """status=pending 待处理；status=done 已处理；不传返回全部。"""
    require_manager(user)
    stmt = apply_scope(select(Approval), Approval, user, View.TEAM)
    if status == "pending":
        stmt = stmt.where(Approval.status == "pending")
    elif status == "done":
        stmt = stmt.where(Approval.status.in_(DONE_STATUSES))
    total = quote_query.count(db, stmt)
    stmt = stmt.order_by(Approval.created_at.desc(), Approval.id)
    rows = list(db.scalars(stmt.offset(page.offset).limit(page.page_size)).all())
    return Page[ApprovalItem](items=to_items(db, rows), total=total)


def _apply_to_target(
    db: Session, user: CurrentUser, approval: Approval, decision: str, source: str
) -> None:
    model: type[Quote] | type[Expense] = Quote if approval.target_type == "quote" else Expense
    target = db.get(model, approval.target_id, with_for_update=True)
    if target is None:
        raise BizError(ErrorCode.NOT_FOUND, "审批对象不存在")
    target.status = TARGET_STATUS[(approval.target_type, decision)]
    verb = "通过" if decision == "approve" else "驳回"
    content = f"主管{verb}了审批" + (f"：{approval.comment}" if approval.comment else "")
    db.flush()
    activity_service.record(
        db, user, approval.target_type, target.id, f"approval_{decision}", content, source, target
    )
    kind = "报价单" if approval.target_type == "quote" else "报销单"
    notification_service.notify(
        db,
        [target.owner_id],
        "approval_decided",
        f"{kind} {target.code} 审批已{verb}",
        approval.comment,
        notification_service.subject_link(approval.target_type, target.id),
    )


def decide(
    db: Session,
    user: CurrentUser,
    approval_id: uuid.UUID,
    decision: str,
    comment: str | None = None,
    source: str = "manual",
) -> ApprovalItem:
    require_manager(user)
    approval = db.get(Approval, approval_id, with_for_update=True)
    ensure_same_team(approval, user)
    assert approval is not None
    if approval.status != "pending":
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "该审批已处理，不能重复决定",
            {"rule": RULE_ALREADY_DECIDED, "status": approval.status},
        )
    if decision not in ("approve", "reject"):
        raise BizError(ErrorCode.VALIDATION, f"未知的审批决定：{decision}")
    approval.status = "approved" if decision == "approve" else "rejected"
    approval.approver_id = user.id
    approval.comment = (comment or "").strip() or None
    approval.decided_at = datetime.now(UTC)
    _apply_to_target(db, user, approval, decision, source)
    return to_items(db, [approval])[0]


def count_pending(db: Session, user: CurrentUser, view: View | None = None) -> int:
    """工作台：销售 = 自己提交且待审批；主管 = 本团队待审批；管理员 = 全部待审批。"""
    stmt = apply_scope(select(Approval).where(Approval.status == "pending"), Approval, user, view)
    return quote_query.count(db, stmt)
