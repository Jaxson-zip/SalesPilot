"""报价单接口（接口契约 §3）：列表、详情、手工新建、状态流转。

状态流转：submit / send / accept / reject / renew / revise；另有复制新版本、草稿补关联。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, Ids, Multi, PageDep
from app.crm.schemas.common import Page
from app.crm.schemas.quote import (
    QuoteCreate,
    QuoteDetail,
    QuoteItemsUpdate,
    QuoteLink,
    QuoteListItem,
    QuoteStatus,
)
from app.crm.services import quote_edit, quote_query, quote_revision, quote_service
from app.crm.services.listing import FacetOption, SortKey, clean, uuids

router = APIRouter(prefix="/api/quotes", tags=["quotes"])
Detail = ApiResponse[QuoteDetail]


def _filter(
    status_in: Multi = None,
    pack: Multi = None,
    customer_in: Ids = None,
    source: Multi = None,
    sort: SortKey | None = None,
) -> quote_query.QuoteFilter:
    return quote_query.QuoteFilter(
        clean(status_in), clean(pack), uuids(customer_in), clean(source), sort
    )


@router.get("", response_model=ApiResponse[Page[QuoteListItem]])
def list_quotes(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    f: Annotated[quote_query.QuoteFilter, Depends(_filter)],
    view: View | None = None,
    status: QuoteStatus | None = None,
    opportunity_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    customer_id: uuid.UUID | None = None,
) -> ApiResponse[Page[QuoteListItem]]:
    """status 是页签（单选）；status_in / pack / customer_in / source 是筛选（多选），同时生效。"""
    return ok(
        quote_service.list_quotes(db, user, view, page, status, opportunity_id, q, customer_id, f)
    )


@router.get("/facets", response_model=ApiResponse[dict[str, list[FacetOption]]])
def quote_facets(
    user: CurrentUserDep, db: DbDep, view: View | None = None
) -> ApiResponse[dict[str, list[FacetOption]]]:
    """列表筛选项：当前范围内出现过的行业包、客户。"""
    return ok(quote_query.facets(db, user, view))


@router.post("", response_model=Detail)
def create_quote(body: QuoteCreate, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_edit.create_manual(db, user, body))


@router.get("/{quote_id}", response_model=Detail)
def get_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(quote_service.get_quote(db, user, quote_id))


@router.patch("/{quote_id}/items", response_model=Detail)
def update_items(
    quote_id: uuid.UUID, body: QuoteItemsUpdate, user: CurrentUserDep, db: DbDep
) -> Detail:
    return ok(quote_edit.update_items(db, user, quote_id, body))


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


@router.post("/{quote_id}/revise", response_model=Detail)
def revise_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    """已审批、还没发给客户的报价撤回修改：退回草稿，改完重新提交审批。"""
    return ok(quote_service.transition(db, user, quote_id, "revise"))


@router.post("/{quote_id}/revisions", response_model=Detail)
def copy_revision(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    """已发送 / 客户拒绝的报价复制为新版本（草稿）；返回新报价。"""
    new_id = quote_revision.copy_revision(db, user, quote_id)
    return ok(quote_service.get_quote(db, user, new_id))


@router.patch("/{quote_id}/link", response_model=Detail)
def link_quote(quote_id: uuid.UUID, body: QuoteLink, user: CurrentUserDep, db: DbDep) -> Detail:
    """草稿补关联客户或商机（AI 没识别出客户时），明细和价格不变。"""
    quote_revision.link(db, user, quote_id, body)
    return ok(quote_service.get_quote(db, user, quote_id))


@router.post("/{quote_id}/renew", response_model=Detail)
def renew_quote(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    """已过有效期的报价退回草稿续期（重新提交后按当天起算有效期）。"""
    return ok(quote_service.transition(db, user, quote_id, "renew"))
