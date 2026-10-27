"""知识库入库：加载（Markdown / PDF / Excel）→ 切块 → 哈希去重 → 经网关向量化 → 写入 kb_chunks。

命令：python -m app.rag.ingest --scope company | pack:llm_deploy | all
"""

import argparse
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.db import session_scope
from app.crm.models import KbChunk
from app.llm.client import embed_texts
from app.packs.registry import list_packs
from app.rag.chunking import Chunk, dedupe, embedding_text
from app.rag.loaders import load_file, supported_files

logger = logging.getLogger("core.rag")
CORE_ROOT = Path(__file__).resolve().parents[2]
COMPANY_DIR = CORE_ROOT / "seed" / "knowledge" / "company"
EMBED_BATCH = 16


def source_dirs() -> dict[str, tuple[Path, str | None]]:
    """scope → (文档目录, 行业包 id)。"""
    dirs: dict[str, tuple[Path, str | None]] = {"company": (COMPANY_DIR, None)}
    for pack in list_packs().values():
        dirs[f"pack:{pack.id}"] = (pack.knowledge_dir, pack.id)
    return dirs


def load_chunks(scope: str) -> list[Chunk]:
    directory, pack = source_dirs()[scope]
    if not directory.exists():
        return []
    return [c for path in supported_files(directory) for c in load_file(path, scope, pack)]


def ingest_scope(db: Session, scope: str) -> int:
    chunks = load_chunks(scope)
    hashes = [c.content_hash for c in chunks]
    existing = set(db.scalars(select(KbChunk.content_hash).where(KbChunk.content_hash.in_(hashes))))
    fresh = dedupe(chunks, existing)
    for start in range(0, len(fresh), EMBED_BATCH):
        batch = fresh[start : start + EMBED_BATCH]
        vectors = embed_texts([embedding_text(c) for c in batch])
        db.add_all(
            KbChunk(
                scope=c.scope,
                pack=c.pack,
                doc_name=c.doc_name,
                section=c.section,
                page=c.page,
                content=c.content,
                content_hash=c.content_hash,
                embedding=v,
            )
            for c, v in zip(batch, vectors, strict=True)
        )
        db.flush()
    logger.info("ingest scope=%s total=%d new=%d", scope, len(chunks), len(fresh))
    return len(fresh)


def ingest(scope: str) -> dict[str, int]:
    scopes = list(source_dirs()) if scope == "all" else [scope]
    with session_scope() as db:
        return {s: ingest_scope(db, s) for s in scopes}


def main() -> None:
    parser = argparse.ArgumentParser(description="知识库入库")
    parser.add_argument("--scope", default="all", help="company | pack:<id> | all")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(ingest(args.scope))


if __name__ == "__main__":
    main()
