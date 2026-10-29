"""客户接口（参考实现）：只做参数和响应，业务逻辑在 customer_service / followup_service。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.audit import client_ip
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.customer import (
    CustomerCreate,
    CustomerDetail,
    CustomerListItem,
    CustomerUpdate,
    PoolRelease,
    SimilarCustomer,
)
from app.crm.schemas.dashboard import (
    ContactIn,
    ContactItem,
    ContactUpdate,
    FollowupIn,
    FollowupItem,
    PhoneOut,
)
from app.crm.schemas.task import CustomerTransfer, HandoverIn, HandoverResult, TransferResult
from app.crm.services import (
    contact_service,
    customer_service,
    followup_service,
    intel_service,
    pool_service,
    transfer_service,
)
from app.crm.services.intel_service import CompanyIntel

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=ApiResponse[Page[CustomerListItem]])
def list_customers(
    user: CurrentUserDep,
    db: DbDep,
    view: View | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[Page[CustomerListItem]]:
    params = PageParams(page=page, page_size=page_size)
    return ok(customer_service.list_customers(db, user, view, q, params))


@router.post("/transfer", response_model=ApiResponse[TransferResult])
def transfer_customers(
    body: CustomerTransfer, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TransferResult]:
    return ok(transfer_service.transfer_customers(db, user, body))


@router.get("/handover/preview", response_model=ApiResponse[HandoverResult])
def preview_handover(
    from_user_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[HandoverResult]:
    return ok(transfer_service.preview_handover(db, user, from_user_id))


@router.post("/handover", response_model=ApiResponse[HandoverResult])
def handover(body: HandoverIn, user: CurrentUserDep, db: DbDep) -> ApiResponse[HandoverResult]:
    return ok(transfer_service.handover(db, user, body))


@router.get("/pool", response_model=ApiResponse[Page[CustomerListItem]])
def list_pool(
    user: CurrentUserDep,
    db: DbDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[Page[CustomerListItem]]:
    """客户公海（B5）：本团队负责人为空的客户。"""
    return ok(pool_service.list_pool(db, user, PageParams(page=page, page_size=page_size)))


@router.post("/{customer_id}/release", response_model=ApiResponse[CustomerDetail])
def release_to_pool(
    customer_id: uuid.UUID, body: PoolRelease, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CustomerDetail]:
    """退回公海：负责人或本团队主管；有进行中的商机时 42201 has_open_opportunities。"""
    return ok(pool_service.release(db, user, customer_id, body.reason))


@router.post("/{customer_id}/claim", response_model=ApiResponse[CustomerDetail])
def claim_from_pool(
    customer_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CustomerDetail]:
    """从公海领取（仅销售，先到先得；已被领取 40901）。"""
    return ok(pool_service.claim(db, user, customer_id))


@router.get("/similar", response_model=ApiResponse[list[SimilarCustomer]])
def similar_customers(
    user: CurrentUserDep, db: DbDep, name: Annotated[str, Query(min_length=1, max_length=200)]
) -> ApiResponse[list[SimilarCustomer]]:
    """新建客户时的查重提示：全公司范围，去掉「有限公司」等后缀后比较。"""
    return ok(customer_service.find_similar(db, user, name))


@router.get("/{customer_id}", response_model=ApiResponse[CustomerDetail])
def get_customer(
    customer_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CustomerDetail]:
    return ok(customer_service.get_customer(db, user, customer_id))


@router.post("", response_model=ApiResponse[CustomerDetail])
def create_customer(
    body: CustomerCreate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CustomerDetail]:
    return ok(customer_service.create_customer(db, user, body))


@router.patch("/{customer_id}", response_model=ApiResponse[CustomerDetail])
def update_customer(
    customer_id: uuid.UUID, body: CustomerUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CustomerDetail]:
    """行内编辑（U10）：只有负责人能改；只修改传入的字段。"""
    return ok(customer_service.update_customer(db, user, customer_id, body))


@router.get("/{customer_id}/followups", response_model=ApiResponse[Page[FollowupItem]])
def list_followups(
    customer_id: uuid.UUID,
    user: CurrentUserDep,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[Page[FollowupItem]]:
    return ok(followup_service.list_for_customer(db, user, customer_id, limit))


@router.post("/{customer_id}/followups", response_model=ApiResponse[FollowupItem])
def create_followup(
    customer_id: uuid.UUID, body: FollowupIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[FollowupItem]:
    return ok(followup_service.create_for_customer(db, user, customer_id, body))


@router.get("/{customer_id}/contacts", response_model=ApiResponse[Page[ContactItem]])
def list_contacts(
    customer_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[Page[ContactItem]]:
    return ok(contact_service.list_contacts(db, user, customer_id))


@router.post("/{customer_id}/contacts", response_model=ApiResponse[ContactItem])
def create_contact(
    customer_id: uuid.UUID, body: ContactIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ContactItem]:
    return ok(contact_service.create_contact(db, user, customer_id, body))


@router.patch("/{customer_id}/contacts/{contact_id}", response_model=ApiResponse[ContactItem])
def update_contact(
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: ContactUpdate,
    user: CurrentUserDep,
    db: DbDep,
) -> ApiResponse[ContactItem]:
    return ok(contact_service.update_contact(db, user, customer_id, contact_id, body))


@router.delete("/{customer_id}/contacts/{contact_id}", response_model=ApiResponse[None])
def delete_contact(
    customer_id: uuid.UUID, contact_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[None]:
    contact_service.delete_contact(db, user, customer_id, contact_id)
    return ok(None)


@router.post("/{customer_id}/contacts/{contact_id}/phone", response_model=ApiResponse[PhoneOut])
def reveal_phone(
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
) -> ApiResponse[PhoneOut]:
    """查看完整电话：记入操作日志，每人每天限次（超出 42901）。"""
    return ok(contact_service.reveal_phone(db, user, customer_id, contact_id, client_ip(request)))


@router.get("/{customer_id}/intel", response_model=ApiResponse[CompanyIntel])
def customer_intel(
    customer_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CompanyIntel]:
    """外部情报：工商信息、新闻舆情、招投标（demo=true 时为演示数据）。"""
    return ok(intel_service.company_intel(db, user, customer_id))
