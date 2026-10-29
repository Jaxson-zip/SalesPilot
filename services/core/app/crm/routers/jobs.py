"""定时任务（仅管理员）：查看、开关 / 改运行时间、立即运行、运行记录。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import job_service
from app.crm.services.job_service import JobItem, JobRunOut, JobUpdate

router = APIRouter(prefix="/api/admin/jobs", tags=["jobs"])


@router.get("", response_model=ApiResponse[list[JobItem]])
def list_jobs(user: CurrentUserDep, db: DbDep) -> ApiResponse[list[JobItem]]:
    return ok(job_service.list_jobs(db, user))


@router.get("/runs", response_model=ApiResponse[list[JobRunOut]])
def list_runs(
    user: CurrentUserDep,
    db: DbDep,
    name: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ApiResponse[list[JobRunOut]]:
    return ok(job_service.list_runs(db, user, name, limit))


@router.patch("/{name}", response_model=ApiResponse[JobItem])
def update_job(name: str, body: JobUpdate, user: CurrentUserDep, db: DbDep) -> ApiResponse[JobItem]:
    return ok(job_service.update_job(db, user, name, body))


@router.post("/{name}/run", response_model=ApiResponse[JobRunOut])
def run_job(name: str, user: CurrentUserDep, db: DbDep) -> ApiResponse[JobRunOut]:
    """立即运行一次（不受开关和时间限制；通知有去重，不会重复提醒）。"""
    return ok(job_service.run_now(db, user, name))
