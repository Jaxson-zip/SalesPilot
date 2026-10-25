"""客户接口（参考实现）：只做参数和响应，业务逻辑在 customer_service。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.auth import CurrentUserDep
from app.common.db import get_db
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.schemas.common import Page, PageParams
from app.crm.schemas.customer import CustomerCreate, CustomerDetail, CustomerListItem
from app.crm.services import customer_service

router = APIRouter(prefix="/api/customers", tags=["customers"])
DbDep = Annotated[Session, Depends(get_db)]


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
