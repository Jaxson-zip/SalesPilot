"""切换知识库向量模型：后台用新模型把全部知识块重新向量化，全部成功后一次性写入并切换分组，
失败不影响现有检索（model_config_service 的内部模块）。"""

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.common.db import session_scope
from app.common.errors import BizError
from app.crm.models import KbChunk
from app.crm.services import model_config_store as store
from app.llm import client
from app.rag.chunking import Chunk, embedding_text
from app.rag.ingest import EMBED_BATCH

logger = logging.getLogger(__name__)

# 进行中的向量重建（只在本进程内）：target, done, total, by, at
JOB: dict[str, Any] = {}
JOB_LOCK = threading.Lock()


def load_chunks(db: Session) -> list[tuple[Any, str]]:
    rows = db.execute(select(KbChunk.id, KbChunk.doc_name, KbChunk.section, KbChunk.content)).all()
    return [(r.id, embedding_text(Chunk("", None, r.doc_name, r.section, r.content))) for r in rows]


def _write_vectors(db: Session, vectors: dict[Any, list[float]]) -> None:
    db.execute(update(KbChunk), [{"id": k, "embedding": v} for k, v in vectors.items()])


def _embed_all(alias: str, chunks: list[tuple[Any, str]], vectors: dict[Any, list[float]]) -> None:
    dims = get_settings().embedding_dims
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        out = client.embed_texts([text for _, text in batch], model=alias)
        if out and len(out[0]) != dims:
            raise store.invalid(f"这个模型输出 {len(out[0])} 维向量，知识库需要 {dims} 维")
        vectors.update((cid, v) for (cid, _), v in zip(batch, out, strict=True))
        JOB["done"] = len(vectors)


def _finish(alias: str, status: dict[str, Any], vectors: dict[Any, list[float]]) -> None:
    with session_scope() as db:
        cfg = store.load(db, lock=True)
        # 重建期间新上传的文档：用新模型补上
        fresh = [c for c in load_chunks(db) if c[0] not in vectors]
        JOB["total"] += len(fresh)
        _embed_all(alias, fresh, vectors)
        _write_vectors(db, vectors)
        cfg.setdefault("groups", {})["embed"] = [alias]
        done = len(vectors)
        cfg["reindex"] = {**status, "status": "done", "total": done, "done": done}
        cfg["reindex"]["at"] = datetime.now(UTC).isoformat()
        store.store(db, None, cfg)
    store.push_quietly(cfg)


def _fail(exc: Exception, status: dict[str, Any], done: int) -> None:
    message = exc.message if isinstance(exc, BizError) else type(exc).__name__
    with session_scope() as db:
        cfg = store.load(db, lock=True)
        cfg["reindex"] = {
            **status,
            "status": "failed",
            "error": message[:300],
            "done": done,
            "total": JOB.get("total", 0),
            "at": datetime.now(UTC).isoformat(),
        }
        store.store(db, None, cfg)


def run(alias: str, by: str) -> None:
    """全部算完再一次性写入并切换分组，中途失败只记录失败原因。"""
    status: dict[str, Any] = {"target": alias, "by": by}
    vectors: dict[Any, list[float]] = {}
    try:
        with session_scope() as db:
            chunks = load_chunks(db)
        JOB["total"] = len(chunks)
        _embed_all(alias, chunks, vectors)
        _finish(alias, status, vectors)
        logger.info("knowledge reindexed with %s: %d chunks", alias, len(vectors))
    except Exception as exc:
        logger.exception("knowledge reindex with %s failed", alias)
        _fail(exc, status, len(vectors))
    finally:
        JOB.clear()


def start(alias: str, by: str, total: int) -> None:
    """占住任务槽再起后台线程；已经有任务在跑就拒绝。"""
    with JOB_LOCK:
        if JOB:
            raise store.invalid("正在重建知识库向量，完成后再切换")
        JOB.update(target=alias, done=0, total=total, by=by)
        JOB["at"] = datetime.now(UTC)
    threading.Thread(target=run, args=(alias, by), name="kb-reindex", daemon=True).start()
