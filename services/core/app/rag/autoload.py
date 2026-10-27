"""启动时自动入库（架构设计 §5.2）：知识库为空且有可用的 Embedding 模型时，后台入库一次。

没有配置 Embedding Key 时只记日志，不影响服务启动；入库失败也只记日志（可手动执行 ingest）。
"""

import logging
import threading
from collections.abc import Callable

from sqlalchemy import func, select

from app.common.config import get_settings
from app.common.db import session_scope
from app.crm.models import KbChunk
from app.llm.client import model_available
from app.rag.ingest import ingest

logger = logging.getLogger("core.rag")


def kb_is_empty() -> bool:
    with session_scope() as db:
        return (db.scalar(select(func.count()).select_from(KbChunk)) or 0) == 0


def decide(empty: Callable[[], bool], embed_ready: Callable[[], bool]) -> str:
    """返回 skip_not_empty / skip_no_embedding / ingest（纯逻辑，便于测试）。"""
    if not empty():
        return "skip_not_empty"
    if not embed_ready():
        return "skip_no_embedding"
    return "ingest"


def _ingest_in_background() -> None:
    try:
        logger.info("knowledge base empty, auto ingest: %s", ingest("all"))
    except Exception:
        logger.exception("auto ingest failed; run `python -m app.rag.ingest --scope all` manually")


def start_auto_ingest() -> str:
    try:
        action = decide(kb_is_empty, lambda: model_available(get_settings().llm_embed_group))
    except Exception:
        logger.warning("auto ingest check failed (database not ready?)", exc_info=True)
        return "skip_error"
    if action == "ingest":
        threading.Thread(target=_ingest_in_background, name="kb-auto-ingest", daemon=True).start()
    else:
        logger.info("auto ingest: %s", action)
    return action
