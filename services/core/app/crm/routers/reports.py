"""销售日报：本人查看事实 / 生成草稿 / 保存提交；主管看团队提交情况与周汇总。"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from starlette.concurrency import run_in_threadpool

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import report_service
from app.crm.services.codes import local_today
from app.crm.services.report_service import (
    DailyReportIn,
    DailyReportOut,
    DraftIn,
    DraftOut,
    SummaryIn,
    SummaryOut,
    TeamDailyOut,
)
from app.llm.client import get_chat_model, model_available

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _llm(request: Request) -> Any:
    rid = getattr(request.state, "request_id", "")
    return get_chat_model(streaming=False, request_id=rid) if model_available(None, rid) else None


@router.get("/daily", response_model=ApiResponse[DailyReportOut])
def get_daily(
    user: CurrentUserDep, db: DbDep, date: Annotated[date | None, Query()] = None
) -> ApiResponse[DailyReportOut]:
    """当天的日报（未写过时 status=none）和系统汇总的事实。"""
    return ok(report_service.get_daily(db, user, date or local_today()))


@router.post("/daily/draft", response_model=ApiResponse[DraftOut])
async def draft_daily(
    body: DraftIn, user: CurrentUserDep, db: DbDep, request: Request
) -> ApiResponse[DraftOut]:
    """AI 按当天事实写草稿（不保存）；无模型时按模板。"""
    d = body.date or local_today()
    out = await run_in_threadpool(report_service.draft_daily, db, user, d, _llm(request))
    return ok(out)


@router.put("/daily", response_model=ApiResponse[DailyReportOut])
def save_daily(body: DailyReportIn, user: CurrentUserDep, db: DbDep) -> ApiResponse[DailyReportOut]:
    return ok(report_service.save_daily(db, user, body))


@router.get("/team", response_model=ApiResponse[TeamDailyOut])
def team_daily(
    user: CurrentUserDep, db: DbDep, date: Annotated[date | None, Query()] = None
) -> ApiResponse[TeamDailyOut]:
    return ok(report_service.team_daily(db, user, date or local_today()))


@router.post("/team/summary", response_model=ApiResponse[SummaryOut])
async def team_summary(
    body: SummaryIn, user: CurrentUserDep, db: DbDep, request: Request
) -> ApiResponse[SummaryOut]:
    """近 N 天（默认 7 天）团队汇总。"""
    out = await run_in_threadpool(report_service.team_summary, db, user, body.days, _llm(request))
    return ok(out)
