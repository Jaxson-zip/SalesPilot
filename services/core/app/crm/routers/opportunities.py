"""商机接口（接口契约 §2）：只做参数和响应，业务逻辑在 opportunity_service。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, PageDep
from app.crm.schemas.common import Page
from app.crm.schemas.opportunity import (
    OpportunityCreate,
    OpportunityDetail,
    OpportunityItem,
    OpportunityUpdate,
    PipelineSummary,
    Stage,
    StageChange,
)
from app.crm.services import opportunity_service

router = APIRouter(prefix="/api", tags=["opportunities"])


@router.get("/opportunities", response_model=ApiResponse[Page[OpportunityItem]])
def list_opportunities(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    view: View | None = None,
    stage: Stage | None = None,
    customer_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> ApiResponse[Page[OpportunityItem]]:
    return ok(opportunity_service.list_opportunities(db, user, view, page, stage, customer_id, q))


@router.get("/opportunities/{opportunity_id}", response_model=ApiResponse[OpportunityDetail])
def get_opportunity(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[OpportunityDetail]:
    return ok(opportunity_service.get_detail(db, user, opportunity_id))


@router.post("/opportunities", response_model=ApiResponse[OpportunityItem])
def create_opportunity(
    body: OpportunityCreate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[OpportunityItem]:
    return ok(opportunity_service.create_opportunity(db, user, body))


@router.patch("/opportunities/{opportunity_id}", response_model=ApiResponse[OpportunityItem])
def update_opportunity(
    opportunity_id: uuid.UUID, body: OpportunityUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[OpportunityItem]:
    return ok(opportunity_service.update_opportunity(db, user, opportunity_id, body))


@router.patch("/opportunities/{opportunity_id}/stage", response_model=ApiResponse[OpportunityItem])
def change_stage(
    opportunity_id: uuid.UUID, body: StageChange, user: CurrentUserDep, db: DbDep
) -> ApiResponse[OpportunityItem]:
    return ok(opportunity_service.change_stage(db, user, opportunity_id, body))


@router.get("/pipeline/summary", response_model=ApiResponse[PipelineSummary])
def pipeline_summary(
    user: CurrentUserDep, db: DbDep, view: View | None = None
) -> ApiResponse[PipelineSummary]:
    return ok(opportunity_service.pipeline_summary(db, user, view))
