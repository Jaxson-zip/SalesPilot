"""客户公海（B5）：负责人为空的客户，留在原团队的公海里。

- 退回：负责人本人或本团队主管，写明原因；客户还有进行中的商机时不能退回（避免商机没人跟）
- 领取：本团队的销售，先到先得（行锁，已被领取返回 40901）
- 主管分配：沿用「转移负责人」（transfer_service，原负责人显示为「公海」）
- 可见性：本团队成员能看到公海客户（只读，scope.can_see），领取后才能修改

退回 / 领取时客户的联系人、跟进、未完成任务、动态一起移动（复用 transfer_service.move_customer）。
"""

import uuid

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import RULE_NOT_OWNER, ensure_business_writer, ensure_role, forbidden
from app.common.scope import ensure_visible
from app.crm.models import Customer, Opportunity
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.customer import CustomerDetail, CustomerListItem
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import activity_service, customer_service
from app.crm.services.transfer_service import move_customer

RULE_OPEN_OPPORTUNITIES = "has_open_opportunities"


def pool_condition(user: CurrentUser) -> ColumnElement[bool]:
    """公海范围：负责人为空；非管理员只看本团队的公海。"""
    cond: ColumnElement[bool] = Customer.owner_id.is_(None)
    if user.role is not Role.ADMIN:
        cond = and_(cond, Customer.team_id == user.team_id)
    return cond


def list_pool(db: Session, user: CurrentUser, page: PageParams) -> Page[CustomerListItem]:
    base = customer_service.build_list_query(user, None, None, scoped=False).where(
        pool_condition(user)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(Customer.updated_at.desc()).offset(page.offset).limit(page.page_size)
    ).all()
    return Page[CustomerListItem](
        items=[customer_service.to_list_item(r) for r in rows], total=int(total)
    )


def release(db: Session, user: CurrentUser, customer_id: uuid.UUID, reason: str) -> CustomerDetail:
    customer = db.get(Customer, customer_id, with_for_update=True)
    ensure_visible(customer, user)
    ensure_business_writer(user)
    assert customer is not None
    is_owner = customer.owner_id == user.id
    is_team_manager = user.role is Role.MANAGER and customer.team_id == user.team_id
    if customer.owner_id is None:
        raise BizError(ErrorCode.DUPLICATE, "客户已经在公海里")
    if not (is_owner or is_team_manager):
        raise forbidden("只有负责人或本团队主管可以退回公海", RULE_NOT_OWNER)
    open_opps = db.scalar(
        select(func.count()).where(
            Opportunity.customer_id == customer.id, Opportunity.stage.not_in(FINAL_STAGES)
        )
    )
    if open_opps:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"客户还有 {open_opps} 个进行中的商机，先结束或转给同事再退回公海",
            {"rule": RULE_OPEN_OPPORTUNITIES, "count": open_opps},
        )
    move_customer(db, customer, {"owner_id": None, "team_id": customer.team_id})
    activity_service.record(
        db, user, "customer", customer.id, "pool_release", reason.strip(), subject=customer
    )
    return customer_service.get_customer(db, user, customer.id)


def claim(db: Session, user: CurrentUser, customer_id: uuid.UUID) -> CustomerDetail:
    ensure_role(user, Role.SALES, "只有销售可以从公海领取客户")
    customer = db.get(Customer, customer_id, with_for_update=True)
    ensure_visible(customer, user)
    assert customer is not None
    if customer.owner_id is not None:
        raise BizError(ErrorCode.DUPLICATE, "这个客户已被领取")
    move_customer(db, customer, {"owner_id": user.id, "team_id": user.team_id})
    activity_service.record(db, user, "customer", customer.id, "pool_claim", None, subject=customer)
    return customer_service.get_customer(db, user, customer.id)
