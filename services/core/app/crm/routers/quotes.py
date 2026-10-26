"""报价单接口（接口契约 §3）：列表、详情、submit / send / accept / reject。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, PageDep
from app.crm.schemas.common import Page
from app.crm.schemas.quote import QuoteDetail, QuoteListItem, QuoteStatus
from app.crm.services import quote_service

router = APIRouter(prefix="/api/quotes", tags=["quotes"])
Detail = ApiResponse[QuoteDetail]


@router.get("", response_model=ApiResponse[Page[QuoteListItem]])
def list_quotes(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    view: View | None = None,
    status: QuoteStatus | None = None,
    opportunity_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    customer_id: uuid.UUID | None = None,
) -> ApiResponse[Page[QuoteListItem]]:
    return ok(
        quote_service.list_quotes(db, user, view, page, status, opportunity_id, q, customer_id)
    )


@router.get("/{quote_id}", response_model=Detail)
def get_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_service.get_quote(db, user, quote_id))


@router.post("/{quote_id}/submit", response_model=Detail)
def submit_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_service.transition(db, user, quote_id, "submit"))


@router.post("/{quote_id}/send", response_model=Detail)
def send_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_service.transition(db, user, quote_id, "send"))


@router.post("/{quote_id}/accept", response_model=Detail)
def accept_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_service.transition(db, user, quote_id, "accept"))


@router.post("/{quote_id}/reject", response_model=Detail)
def reject_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_service.transition(db, user, quote_id, "reject"))
