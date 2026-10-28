"""操作日志、导出登记。"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import Page, PageParams
from app.crm.services import audit_service
from app.crm.services.audit_service import AuditFilter, AuditItem, ExportIn, ExportOut

router = APIRouter(prefix="/api", tags=["audit"])


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


@router.get("/audit-logs", response_model=ApiResponse[Page[AuditItem]])
def list_audit_logs(
    user: CurrentUserDep,
    db: DbDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    user_id: uuid.UUID | None = None,
    result: Literal["ok", "failed"] | None = None,
    source: Literal["web", "agent"] | None = None,
    date_from: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    date_to: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[Page[AuditItem]]:
    """管理员看全公司，主管看本团队，销售 40301。"""
    f = AuditFilter.model_validate(
        {
            "q": q,
            "action": action,
            "user_id": user_id,
            "ok": None if result is None else result == "ok",
            "source": source,
            "date_from": date_from,
            "date_to": date_to,
        }
    )
    params = PageParams(page=page, page_size=page_size)
    return ok(audit_service.list_logs(db, user, f, params))


@router.post("/exports", response_model=ApiResponse[ExportOut])
def register_export(
    body: ExportIn, user: CurrentUserDep, db: DbDep, request: Request
) -> ApiResponse[ExportOut]:
    """前端导出 CSV 之前登记：按角色授权、限制条数，并记入操作日志。"""
    return ok(audit_service.check_export(db, user, body, client_ip(request)))
