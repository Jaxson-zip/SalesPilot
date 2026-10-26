"""审批接口（接口契约 §6，仅 manager；角色校验在 approval_service）。"""

import uuid
from typing import Literal

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep, PageDep
from app.crm.schemas.common import Page
from app.crm.schemas.finance import ApprovalDecision, ApprovalItem
from app.crm.services import approval_service

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=ApiResponse[Page[ApprovalItem]])
def list_approvals(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    status: Literal["pending", "done"] | None = None,
) -> ApiResponse[Page[ApprovalItem]]:
    return ok(approval_service.list_approvals(db, user, status, page))


@router.post("/{approval_id}/decide", response_model=ApiResponse[ApprovalItem])
def decide(
    approval_id: uuid.UUID, body: ApprovalDecision, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ApprovalItem]:
    return ok(approval_service.decide(db, user, approval_id, body.decision, body.comment))
