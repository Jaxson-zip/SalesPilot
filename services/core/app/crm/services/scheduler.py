"""进程内调度器：每 30 秒调用一次 job_service.tick（数据库保证同一任务一天只跑一次）。

在 FastAPI lifespan 里启动 / 停止；SCHEDULER_ENABLED=false 时不启动（测试、只读副本）。
"""

import asyncio
import contextlib
import logging

from starlette.concurrency import run_in_threadpool

from app.crm.services import job_service

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 30


async def _loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await run_in_threadpool(job_service.tick)
        except Exception:  # 数据库暂时不可用等：记日志，下一轮再试
            logger.exception("scheduler tick failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL_SECONDS)


class Scheduler:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(_loop(self._stop), name="scheduler")
        logger.info("scheduler started (every %ss)", INTERVAL_SECONDS)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
