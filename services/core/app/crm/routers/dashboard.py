"""工作台接口（接口契约 §1）：指标卡 + 漏斗、动态流。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import ActivityOut, Page
from app.crm.schemas.dashboard import Dashboard
from app.crm.services import activity_service, dashboard_service

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=ApiResponse[Dashboard])
def get_dashboard(
    user: CurrentUserDep, db: DbDep, view: View | None = None
) -> ApiResponse[Dashboard]:
    return ok(dashboard_service.get_dashboard(db, user, view))


@router.get("/activities", response_model=ApiResponse[Page[ActivityOut]])
def list_activities(
    user: CurrentUserDep,
    db: DbDep,
    view: View | None = None,
    subject_type: Annotated[str | None, Query(max_length=20)] = None,
    subject_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[Page[ActivityOut]]:
    items = activity_service.list_activities(db, user, view, subject_type, subject_id, limit)
    return ok(Page[ActivityOut](items=items, total=len(items)))
