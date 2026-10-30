"""FastAPI 入口：挂载路由、/health、X-Request-ID 中间件、全局异常处理。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.agent.checkpoint import close_checkpointer, init_checkpointer
from app.agent.router import router as agent_router
from app.common import preflight
from app.common.config import get_settings
from app.common.db import check_db
from app.common.request_id import RequestIdMiddleware
from app.common.response import ApiResponse, ok, register_exception_handlers
from app.crm.audit_middleware import AuditMiddleware
from app.crm.routers import (
    accounts,
    approvals,
    audit,
    auth,
    competitors,
    contracts,
    customers,
    dashboard,
    expenses,
    integrations,
    jobs,
    notifications,
    opportunities,
    product_lines,
    quotes,
    reports,
    rules,
    settings,
    targets,
    tasks,
    usage,
)
from app.crm.services.scheduler import Scheduler
from app.rag.autoload import start_auto_ingest
from app.rules.overrides import refresh_on_startup as refresh_overrides

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("core")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = get_settings()
    found = preflight.problems(cfg)
    if found and not cfg.demo_login:
        # 正式模式：默认密钥能伪造登录、默认数据库密码能直接读库，宁可起不来
        raise RuntimeError("正式模式（DEMO_LOGIN=false）拒绝启动：" + "；".join(found))
    for problem in found:
        logger.warning("insecure config (ok for local demo, not for production): %s", problem)
    db_ok = await run_in_threadpool(check_db)
    if not db_ok:
        logger.warning("database unavailable at startup; DB-backed endpoints will fail")
    saver = await run_in_threadpool(init_checkpointer, db_ok)
    app.state.checkpointer_kind = type(saver).__name__
    if db_ok:
        await run_in_threadpool(refresh_overrides)  # 网页上改过的规则 / 价格
        app.state.kb_autoload = await run_in_threadpool(start_auto_ingest)
    scheduler = Scheduler() if db_ok and cfg.scheduler_enabled else None
    if scheduler is not None:
        scheduler.start()
    yield
    if scheduler is not None:
        await scheduler.stop()
    await run_in_threadpool(close_checkpointer)


def create_app() -> FastAPI:
    app = FastAPI(title="SalesPilot Core", version="0.1.0", lifespan=lifespan)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    routers = (
        auth.router,
        accounts.router,
        jobs.router,
        audit.router,
        competitors.router,
        integrations.router,
        reports.router,
        usage.router,
        customers.router,
        rules.router,
        dashboard.router,
        opportunities.router,
        quotes.router,
        contracts.router,
        expenses.router,
        approvals.router,
        product_lines.router,
        settings.router,
        targets.router,
        tasks.router,
        notifications.router,
        agent_router,
    )
    for router in routers:
        app.include_router(router)
    app.add_api_route(
        "/health", health, methods=["GET"], response_model=ApiResponse[Health], tags=["health"]
    )
    return app


class Health(BaseModel):
    status: str
    db: bool
    checkpointer: str


async def health(request: Request) -> ApiResponse[Health]:
    """服务存活即返回 code=0；数据库不可用时 status=degraded、db=false。"""
    db_ok = await run_in_threadpool(check_db)
    kind = getattr(request.app.state, "checkpointer_kind", "unknown")
    return ok(Health(status="ok" if db_ok else "degraded", db=db_ok, checkpointer=kind))


app = create_app()
