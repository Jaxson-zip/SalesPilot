"""FastAPI 入口：挂载路由、/health、X-Request-ID 中间件、全局异常处理。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.agent.checkpoint import close_checkpointer, init_checkpointer, is_persistent
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
    feedback,
    integrations,
    jobs,
    notifications,
    opportunities,
    product_lines,
    quotes,
    reports,
    rules,
    settings,
    shares,
    targets,
    tasks,
    usage,
)
from app.crm.services import model_config_service
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
    if not cfg.demo_login and not is_persistent():
        # 正式模式：会话存在内存里，重启就丢（包括等待确认的报价、报销），宁可起不来让容器重试
        raise RuntimeError("正式模式（DEMO_LOGIN=false）拒绝启动：会话存储连不上 Postgres")
    if db_ok:
        await run_in_threadpool(refresh_overrides)  # 网页上改过的规则 / 价格
        app.state.kb_autoload = await run_in_threadpool(start_auto_ingest)
    scheduler = Scheduler() if db_ok and cfg.scheduler_enabled else None
    if scheduler is not None:
        scheduler.start()
    # 网页上的模型配置：推给网关，之后每分钟比对一次（网关重启会丢）；测试里不启动
    key_sync = model_config_service.start_sync() if db_ok and cfg.scheduler_enabled else None
    yield
    if key_sync is not None:
        key_sync.set()
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
        feedback.router,
        customers.router,
        rules.router,
        dashboard.router,
        opportunities.router,
        quotes.router,
        shares.router,
        shares.public_router,
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
    # /health 给容器内部（compose healthcheck）用；/api/health 经 nginx 对外，供监控和发布核对版本
    for path in ("/health", "/api/health"):
        app.add_api_route(
            path, health, methods=["GET"], response_model=ApiResponse[Health], tags=["health"]
        )
    app.add_api_route(
        "/api/readyz", readyz, methods=["GET"], response_model=ApiResponse[Health], tags=["health"]
    )
    return app


class Health(BaseModel):
    status: str
    db: bool
    checkpointer: str
    persistent: bool = False  # 会话存在 Postgres（进程重启不丢）
    version: str = "dev"  # 构建时的提交 SHA


async def health(request: Request) -> ApiResponse[Health]:
    """服务存活即返回 code=0。数据库不可用，或会话存储退回到内存（重启会丢会话）时
    status=degraded；发布流水线的就绪检查要求 status=ok。"""
    db_ok = await run_in_threadpool(check_db)
    kind = getattr(request.app.state, "checkpointer_kind", "unknown")
    persistent = is_persistent()
    status = "ok" if db_ok and persistent else "degraded"
    version = get_settings().app_version
    out = Health(status=status, db=db_ok, checkpointer=kind, persistent=persistent, version=version)
    return ok(out)


async def readyz(request: Request, response: Response) -> ApiResponse[Health]:
    """就绪检查：内容同 /api/health，没就绪时 HTTP 503，外部监控 / 负载均衡只看状态码即可。"""
    body = await health(request)
    if body.data is None or body.data.status != "ok":
        response.status_code = 503
    return body


app = create_app()
