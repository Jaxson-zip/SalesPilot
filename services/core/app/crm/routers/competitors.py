"""竞品战卡：查询（所有角色）、维护（管理员）、商机标注竞品（负责人）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import competitor_service
from app.crm.services.competitor_service import CompetitorIn, CompetitorOut, OppCompetitorsIn

router = APIRouter(prefix="/api", tags=["competitors"])


@router.get("/competitors", response_model=ApiResponse[list[CompetitorOut]])
def list_competitors(
    user: CurrentUserDep, db: DbDep, q: Annotated[str | None, Query(max_length=100)] = None
) -> ApiResponse[list[CompetitorOut]]:
    """q 匹配名称、别名、弱点、打法和常见说法（现场按客户原话搜）。"""
    return ok(competitor_service.list_competitors(db, q))


@router.post("/competitors", response_model=ApiResponse[CompetitorOut])
def create_competitor(
    body: CompetitorIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CompetitorOut]:
    return ok(competitor_service.create_competitor(db, user, body))


@router.put("/competitors/{competitor_id}", response_model=ApiResponse[CompetitorOut])
def update_competitor(
    competitor_id: uuid.UUID, body: CompetitorIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[CompetitorOut]:
    return ok(competitor_service.update_competitor(db, user, competitor_id, body))


@router.delete("/competitors/{competitor_id}", response_model=ApiResponse[None])
def delete_competitor(
    competitor_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[None]:
    competitor_service.delete_competitor(db, user, competitor_id)
    return ok(None)


@router.get(
    "/opportunities/{opportunity_id}/competitors", response_model=ApiResponse[list[CompetitorOut]]
)
def opportunity_competitors(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[list[CompetitorOut]]:
    return ok(competitor_service.opportunity_competitors(db, user, opportunity_id))


@router.put(
    "/opportunities/{opportunity_id}/competitors", response_model=ApiResponse[list[CompetitorOut]]
)
def set_opportunity_competitors(
    opportunity_id: uuid.UUID, body: OppCompetitorsIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[list[CompetitorOut]]:
    """覆盖式设置商机遇到的竞品（仅负责人）。"""
    return ok(competitor_service.set_opportunity_competitors(db, user, opportunity_id, body))
