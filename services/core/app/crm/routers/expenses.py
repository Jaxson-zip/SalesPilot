"""报销与票据接口（接口契约 §5）。下载接口直接返回文件流，其余为统一响应。"""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, Multi, PageDep
from app.crm.schemas.common import AttachmentKind, AttachmentOut, Page
from app.crm.schemas.finance import ExpenseCreate, ExpenseDetail, ExpenseItem, ExpenseStatus
from app.crm.services import attachment_service, expense_service
from app.crm.services.expense_filter import ExpenseFilter
from app.crm.services.listing import SortKey, clean

router = APIRouter(prefix="/api", tags=["expenses"])


def _filter(
    type: Multi = None,
    status_in: Multi = None,
    over: Multi = None,
    sort: SortKey | None = None,
    opportunity_id: uuid.UUID | None = None,
) -> ExpenseFilter:
    return ExpenseFilter(clean(type), clean(status_in), clean(over), sort, opportunity_id)


Detail = ApiResponse[ExpenseDetail]


@router.get("/expenses", response_model=ApiResponse[Page[ExpenseItem]])
def list_expenses(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    f: Annotated[ExpenseFilter, Depends(_filter)],
    view: View | None = None,
    status: ExpenseStatus | None = None,
) -> ApiResponse[Page[ExpenseItem]]:
    """status 是页签；type / status_in / over（yes | no）是筛选（多选）。"""
    return ok(expense_service.list_expenses(db, user, view, page, status, f))


@router.get("/expenses/{expense_id}", response_model=Detail)
def get_expense(expense_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(expense_service.get_expense(db, user, expense_id))


@router.post("/expenses", response_model=Detail)
def create_expense(body: ExpenseCreate, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(expense_service.create_expense(db, user, body))


@router.put("/expenses/{expense_id}", response_model=Detail)
def update_expense(
    expense_id: uuid.UUID, body: ExpenseCreate, user: CurrentUserDep, db: DbDep
) -> Detail:
    return ok(expense_service.update_expense(db, user, expense_id, body))


@router.delete("/expenses/{expense_id}", response_model=ApiResponse[None])
def delete_expense(expense_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> ApiResponse[None]:
    expense_service.delete_draft(db, user, expense_id)
    return ok(None)


@router.post("/expenses/{expense_id}/submit", response_model=Detail)
def submit_expense(expense_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    return ok(expense_service.submit_expense(db, user, expense_id))


@router.post("/expenses/{expense_id}/attachments", response_model=ApiResponse[AttachmentOut])
def upload_attachment(
    expense_id: uuid.UUID,
    user: CurrentUserDep,
    db: DbDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[AttachmentKind, Form()] = "other",
) -> ApiResponse[AttachmentOut]:
    name = file.filename or "file"
    return ok(attachment_service.upload(db, user, expense_id, kind, name, file.file))


@router.delete("/attachments/{attachment_id}", response_model=ApiResponse[None])
def delete_attachment(
    attachment_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[None]:
    attachment_service.delete(db, user, attachment_id)
    return ok(None)


@router.get("/attachments/{attachment_id}/file", response_class=FileResponse)
def download_attachment(attachment_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> FileResponse:
    path, mime, name = attachment_service.file_for_download(db, user, attachment_id)
    disposition = "inline; filename*=UTF-8''" + quote(name)
    return FileResponse(path, media_type=mime, headers={"Content-Disposition": disposition})
