"""客户接口（参考实现）：只做参数和响应，业务逻辑在 customer_service / followup_service。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.customer import CustomerCreate, CustomerDetail, CustomerListItem
from app.crm.schemas.dashboard import ContactItem, FollowupIn, FollowupItem
from app.crm.schemas.task import CustomerTransfer, TransferResult
from app.crm.services import customer_service, followup_service, transfer_service

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
    return ok(customer_service.list_contacts(db, user, customer_id))
