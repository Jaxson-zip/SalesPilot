"""商机接口（接口契约 §2）：只做参数和响应，业务逻辑在 opportunity_service。"""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.agent.sse import to_sse
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
from app.crm.services import (
    meddic_service,
    opportunity_service,
    prd_service,
    requirement_service,
    suggestion_service,
    usage_service,
)
from app.crm.services.meddic_service import AssessOut, MeddicOut, MeddicUpdate
from app.crm.services.requirement_service import RequirementOut
from app.crm.services.suggestion_service import DealSuggestion
from app.llm.client import get_chat_model, model_available

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


@router.get(
    "/opportunities/{opportunity_id}/suggestions", response_model=ApiResponse[list[DealSuggestion]]
)
def opportunity_suggestions(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[list[DealSuggestion]]:
    """这单的下一步建议（规则计算）：每条带一句交给 AI 的话。"""
    return ok(suggestion_service.opportunity_suggestions(db, user, opportunity_id))


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


@router.get(
    "/opportunities/{opportunity_id}/requirement",
    response_model=ApiResponse[RequirementOut | None],
)
def get_requirement(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[RequirementOut | None]:
    """出方案时保存的需求清单（还没出过方案时 data 为 null）。"""
    return ok(requirement_service.get_requirement(db, user, opportunity_id))


@router.get(
    "/opportunities/{opportunity_id}/requirement/prd",
    response_model=ApiResponse[prd_service.PrdOut | None],
)
def get_prd(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[prd_service.PrdOut | None]:
    """按需求清单生成过的 PRD 规格书（没生成过为 null；需求之后改过时 stale=true）。"""
    return ok(prd_service.get_prd(db, user, opportunity_id))


@router.post("/opportunities/{opportunity_id}/requirement/prd")
async def generate_prd(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep, request: Request
) -> EventSourceResponse:
    """生成 / 重新生成 PRD（SSE，事件与 AI 对话一致）：message.delta → artifact{type: prd} → done。

    篇幅较长，用流式避免网关和代理超时；模型不可用时直接给模板版。只有负责人本人可以生成。
    """
    await run_in_threadpool(usage_service.ensure_daily_quota, user)
    job = await run_in_threadpool(prd_service.prepare, db, user, opportunity_id)
    rid = getattr(request.state, "request_id", "")
    llm = get_chat_model(temperature=0.3, request_id=rid) if model_available(None, rid) else None

    async def events() -> AsyncIterator[dict[str, str]]:
        async for e in iterate_in_threadpool(prd_service.run(user, job, llm)):
            yield to_sse(e)

    return EventSourceResponse(events())


@router.get("/opportunities/{opportunity_id}/meddic", response_model=ApiResponse[MeddicOut])
def get_meddic(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[MeddicOut]:
    """MEDDIC 赢单要素：6 项状态、证据、未确认项的建议问题、按阶段的风险。"""
    return ok(meddic_service.get_meddic(db, user, opportunity_id))


@router.put("/opportunities/{opportunity_id}/meddic", response_model=ApiResponse[MeddicOut])
def update_meddic(
    opportunity_id: uuid.UUID, body: MeddicUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[MeddicOut]:
    """只有负责人本人可以修改（传哪几项改哪几项）。"""
    return ok(meddic_service.update_meddic(db, user, opportunity_id, body))


@router.post("/opportunities/{opportunity_id}/meddic/assess", response_model=ApiResponse[AssessOut])
async def assess_meddic(
    opportunity_id: uuid.UUID, user: CurrentUserDep, db: DbDep, request: Request
) -> ApiResponse[AssessOut]:
    """AI 根据跟进记录和联系人评估各项（只是建议，不保存）；没有可用模型时按规则判断。"""
    rid = getattr(request.state, "request_id", "")
    llm = get_chat_model(streaming=False, request_id=rid) if model_available(None, rid) else None
    out = await run_in_threadpool(meddic_service.assess, db, user, opportunity_id, llm)
    return ok(out)
