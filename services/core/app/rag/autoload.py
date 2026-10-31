"""启动时自动入库（架构设计 §5.2）：有文档但还没入库的分区（新加的行业包、知识库为空），
在有可用的 Embedding 模型时后台补入库。

原来只在整个知识库为空时入库：后加的行业包（如软件外包）永远进不了库，检索时查不到它的文档。
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
from app.rag.ingest import ingest_scope, load_chunks, source_dirs

logger = logging.getLogger("core.rag")


def missing_scopes() -> list[str]:
    """有可入库的文档、但库里一个切块都没有的分区。"""
    with session_scope() as db:
        counts = dict(db.execute(select(KbChunk.scope, func.count()).group_by(KbChunk.scope)).all())
    return [s for s in source_dirs() if not counts.get(s) and load_chunks(s)]


def decide(missing: Callable[[], list[str]], embed_ready: Callable[[], bool]) -> str:
    """返回 skip_up_to_date / skip_no_embedding / ingest（纯逻辑，便于测试）。"""
    if not missing():
        return "skip_up_to_date"
    if not embed_ready():
        return "skip_no_embedding"
    return "ingest"


def _ingest_in_background(scopes: list[str]) -> None:
    for scope in scopes:
        try:
            with session_scope() as db:
                logger.info("auto ingest scope=%s new=%d", scope, ingest_scope(db, scope))
        except Exception:
            logger.exception(
                "auto ingest %s failed; run `python -m app.rag.ingest --scope %s`", scope, scope
            )


def start_auto_ingest() -> str:
    try:
        scopes = missing_scopes()
        action = decide(lambda: scopes, lambda: model_available(get_settings().llm_embed_group))
    except Exception:
        logger.warning("auto ingest check failed (database not ready?)", exc_info=True)
        return "skip_error"
    if action == "ingest":
        threading.Thread(
            target=_ingest_in_background, args=(scopes,), name="kb-auto-ingest", daemon=True
        ).start()
    else:
        logger.info("auto ingest: %s", action)
    return action
