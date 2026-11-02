"""LangGraph checkpointer：数据库可用时用 Postgres（会话可跨重启恢复），否则退回内存。"""

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from app.common.config import get_settings

logger = logging.getLogger("core.agent")
_saver: BaseCheckpointSaver | None = None
_pool: object | None = None


def _plain_dsn(url: str) -> str:
    """SQLAlchemy URL（postgresql+psycopg://）→ libpq DSN（postgresql://）。"""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def init_checkpointer(use_postgres: bool) -> BaseCheckpointSaver:
    global _saver, _pool
    if use_postgres:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            pool = ConnectionPool(
                _plain_dsn(get_settings().database_url),
                min_size=1,
                max_size=5,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                open=True,
            )
            saver = PostgresSaver(pool)  # type: ignore[arg-type]
            saver.setup()
            _pool, _saver = pool, saver
            logger.info("checkpointer: postgres")
            return saver
        except Exception:
            logger.warning("checkpointer: postgres unavailable, fallback to memory", exc_info=True)
    _saver = InMemorySaver()
    logger.info("checkpointer: memory")
    return _saver


def is_persistent() -> bool:
    """会话是否存在 Postgres（进程重启不丢）。

    退回内存后不会自动切回：/health 报 degraded，重启 core 恢复。"""
    return _pool is not None


def get_checkpointer() -> BaseCheckpointSaver:
    return _saver if _saver is not None else init_checkpointer(use_postgres=False)


def close_checkpointer() -> None:
    global _saver, _pool
    close = getattr(_pool, "close", None)
    if callable(close):
        close()
    _saver, _pool = None, None
