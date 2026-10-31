"""定时任务：配置（仅管理员）、执行与运行记录。

自动运行：调度器每 30 秒看一次，任务开启、到了当天的运行时间（工作日任务跳过周末）、
今天还没跑过 → 运行。
「今天还没跑过」靠 job_runs 的 (job, run_key=日期) 唯一约束保证：多个实例同时检查也只有一个能抢到。
core 在运行时间没启动时，当天启动后补跑；更早的不补。
"""

import logging
import uuid
from datetime import UTC, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_configurer
from app.crm.models import JobRun, ScheduledJob, User
from app.crm.services.jobs import JOBS, JobDef, new_run_key
from app.rules.crm_calc import LOCAL_TZ

logger = logging.getLogger(__name__)

RUN_HISTORY = 50


class JobRunOut(BaseModel):
    id: uuid.UUID
    job: str
    trigger: Literal["auto", "manual"]
    triggered_by: str | None = None  # 手动运行的人
    status: Literal["running", "ok", "failed"]
    summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class JobOption(BaseModel):
    key: str
    value: int


class JobItem(BaseModel):
    name: str
    title: str
    description: str
    enabled: bool
    run_at: str  # HH:MM（北京时间）
    weekdays_only: bool
    options: list[JobOption]
    last_run: JobRunOut | None = None


class JobUpdate(BaseModel):
    enabled: bool | None = None
    run_at: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    options: dict[str, int] | None = None


def _ensure_admin(user: CurrentUser) -> None:
    ensure_configurer(user, "定时任务由系统管理员配置")


def _def(name: str) -> JobDef:
    job = JOBS.get(name)
    if job is None:
        raise BizError(ErrorCode.NOT_FOUND, "没有这个定时任务")
    return job


def config(db: Session, job: JobDef) -> tuple[bool, time, dict[str, Any]]:
    """（开关, 运行时间, 参数）：网页上改过的优先，否则用默认值。"""
    row = db.get(ScheduledJob, job.name)
    options = {k: v for k, v in job.options}
    if row is None:
        return job.enabled, job.run_at, options
    options.update({k: v for k, v in (row.options or {}).items() if k in options})
    return row.enabled, row.run_at, options


def _run_out(run: JobRun, names: dict[uuid.UUID, str]) -> JobRunOut:
    return JobRunOut(
        id=run.id,
        job=run.job,
        trigger=run.trigger,  # type: ignore[arg-type]
        triggered_by=names.get(run.triggered_by) if run.triggered_by else None,
        status=run.status,  # type: ignore[arg-type]
        summary=run.summary,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _names(db: Session, runs: list[JobRun]) -> dict[uuid.UUID, str]:
    ids = {r.triggered_by for r in runs if r.triggered_by}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all())


def _item(db: Session, job: JobDef) -> JobItem:
    enabled, run_at, options = config(db, job)
    last = db.scalar(
        select(JobRun).where(JobRun.job == job.name).order_by(JobRun.started_at.desc()).limit(1)
    )
    return JobItem(
        name=job.name,
        title=job.title,
        description=job.description,
        enabled=enabled,
        run_at=run_at.strftime("%H:%M"),
        weekdays_only=job.weekdays_only,
        options=[JobOption(key=k, value=v) for k, v in options.items()],
        last_run=_run_out(last, _names(db, [last])) if last else None,
    )


def list_jobs(db: Session, user: CurrentUser) -> list[JobItem]:
    _ensure_admin(user)
    return [_item(db, j) for j in JOBS.values()]


def update_job(db: Session, user: CurrentUser, name: str, body: JobUpdate) -> JobItem:
    _ensure_admin(user)
    job = _def(name)
    enabled, run_at, options = config(db, job)
    if body.options:
        unknown = set(body.options) - set(options)
        if unknown:
            raise BizError(ErrorCode.VALIDATION, f"不支持的参数：{'、'.join(sorted(unknown))}")
        if any(v < 1 or v > 3650 for v in body.options.values()):
            raise BizError(ErrorCode.VALIDATION, "天数要在 1～3650 之间")
        options.update(body.options)
    if body.run_at is not None:
        hh, mm = body.run_at.split(":")
        run_at = time(int(hh), int(mm))
    values = {
        "enabled": enabled if body.enabled is None else body.enabled,
        "run_at": run_at,
        "options": options,
        "updated_by": user.id,
    }
    stmt = insert(ScheduledJob).values(name=name, **values)
    db.execute(stmt.on_conflict_do_update(index_elements=["name"], set_=values))
    db.flush()
    db.expire_all()
    return _item(db, job)


def list_runs(
    db: Session, user: CurrentUser, name: str | None = None, limit: int = 20
) -> list[JobRunOut]:
    _ensure_admin(user)
    stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(min(limit, RUN_HISTORY))
    if name:
        stmt = stmt.where(JobRun.job == _def(name).name)
    runs = list(db.scalars(stmt))
    names = _names(db, runs)
    return [_run_out(r, names) for r in runs]


# ---------- 执行 ----------


def _claim(name: str, run_key: str, trigger: str, user_id: uuid.UUID | None) -> uuid.UUID | None:
    """登记一次运行；(job, run_key) 已存在（今天已经跑过 / 别的实例正在跑）时返回 None。"""
    with session_scope() as db:
        stmt = (
            insert(JobRun)
            .values(
                id=uuid.uuid4(),
                job=name,
                run_key=run_key,
                trigger=trigger,
                triggered_by=user_id,
                status="running",
            )
            .on_conflict_do_nothing(constraint="uq_job_runs_job_run_key")
            .returning(JobRun.id)
        )
        return db.scalar(stmt)


def _finish(run_id: uuid.UUID, status: str, summary: str) -> None:
    with session_scope() as db:
        db.execute(
            update(JobRun)
            .where(JobRun.id == run_id)
            .values(status=status, summary=summary[:500], finished_at=datetime.now(UTC))
        )


def execute(
    name: str,
    now: datetime,
    *,
    run_key: str,
    trigger: Literal["auto", "manual"],
    user_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """运行一次（任务本身在独立事务里，失败只回滚任务的改动，运行记录照样写成 failed）。"""
    job = _def(name)
    run_id = _claim(name, run_key, trigger, user_id)
    if run_id is None:
        return None
    try:
        with session_scope() as db:
            _, _, options = config(db, job)
            summary = job.run(db, now, options)
    except Exception as exc:
        logger.exception("scheduled job %s failed", name)
        _finish(run_id, "failed", f"运行出错：{type(exc).__name__}: {exc}")
    else:
        logger.info("scheduled job %s: %s", name, summary)
        _finish(run_id, "ok", summary)
    return run_id


def run_now(db: Session, user: CurrentUser, name: str) -> JobRunOut:
    """管理员「立即运行」：不受开关和时间限制；通知有去重，不会重复提醒。"""
    _ensure_admin(user)
    _def(name)
    run_id = execute(
        name, datetime.now(UTC), run_key=new_run_key(), trigger="manual", user_id=user.id
    )
    assert run_id is not None
    run = db.get(JobRun, run_id)
    assert run is not None
    db.refresh(run)
    return _run_out(run, _names(db, [run]))


def due(now: datetime) -> list[str]:
    """此刻应该自动运行、但今天还没跑过的任务。"""
    local = now.astimezone(LOCAL_TZ)
    key = local.date().isoformat()
    out: list[str] = []
    with session_scope() as db:
        done = set(db.scalars(select(JobRun.job).where(JobRun.run_key == key)))
        for job in JOBS.values():
            enabled, run_at, _ = config(db, job)
            if not enabled or job.name in done or local.time() < run_at:
                continue
            if job.weekdays_only and local.weekday() >= 5:
                continue
            out.append(job.name)
    return out


def tick(now: datetime | None = None) -> list[str]:
    """调度器每次检查调用：运行到点的任务，返回实际运行了的任务名。"""
    current = now or datetime.now(UTC)
    key = current.astimezone(LOCAL_TZ).date().isoformat()
    ran: list[str] = []
    for name in due(current):
        if execute(name, current, run_key=key, trigger="auto") is not None:
            ran.append(name)
    return ran
