"""检索：按 scope 过滤（公司制度 + 当前行业包）→ 余弦相似度 top_k=8 → 阈值 0.5 → 重排取前 4。

没有任何片段超过阈值时返回 found=false；只返回片段和出处，不决定回答内容。
是否拒答只看向量相似度阈值；重排只调整命中片段的顺序，重排不可用时保持向量顺序。
"""

import logging

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.common.errors import BizError
from app.crm.models import KbChunk
from app.llm.client import embed_texts, rerank_texts

logger = logging.getLogger("core.rag")
TOP_K = 8
THRESHOLD = 0.5
RERANK_TOP = 4


class Source(BaseModel):
    content: str
    doc_name: str
    section: str | None
    score: float
    page: int | None = None  # PDF 的页码
    rerank_score: float | None = None  # 经过重排时的相关度


class PolicySearchResult(BaseModel):
    found: bool
    sources: list[Source]


def scopes_for(pack_id: str | None) -> list[str]:
    return ["company"] + ([f"pack:{pack_id}"] if pack_id else [])


def filter_hits(hits: list[Source], threshold: float = THRESHOLD) -> PolicySearchResult:
    kept = sorted((h for h in hits if h.score >= threshold), key=lambda h: -h.score)
    return PolicySearchResult(found=bool(kept), sources=kept)


def search(
    db: Session,
    query: str,
    scopes: list[str],
    *,
    top_k: int = TOP_K,
    threshold: float = THRESHOLD,
    request_id: str | None = None,
    rerank: bool | None = None,
) -> PolicySearchResult:
    vector = embed_texts([query], request_id=request_id)[0]
    distance = KbChunk.embedding.cosine_distance(vector)
    stmt = (
        select(KbChunk, distance.label("distance"))
        .where(KbChunk.scope.in_(scopes), KbChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )
    hits = [
        Source(
            content=row.KbChunk.content,
            doc_name=row.KbChunk.doc_name,
            section=row.KbChunk.section,
            score=round(1 - float(row.distance), 4),
            page=row.KbChunk.page,
        )
        for row in db.execute(stmt).all()
    ]
    result = filter_hits(hits, threshold)
    if rerank is None:
        rerank = get_settings().rag_rerank
    if rerank and result.found:
        ranked = rerank_hits(query, result.sources, request_id)
        result = PolicySearchResult(found=True, sources=ranked)
    return result


def rerank_hits(
    query: str, hits: list[Source], request_id: str | None = None, top_n: int = RERANK_TOP
) -> list[Source]:
    """经网关重排并取前 top_n；重排失败时保持向量顺序（同样取前 top_n），不影响回答。"""
    if len(hits) <= 1:
        return hits
    try:
        ranked = rerank_texts(query, [h.content for h in hits], top_n=top_n, request_id=request_id)
    except BizError as exc:
        logger.warning("rerank unavailable, keep vector order: %s", exc)
        return hits[:top_n]
    out = [hits[i].model_copy(update={"rerank_score": round(score, 4)}) for i, score in ranked]
    return out[:top_n] or hits[:top_n]


def source_title(source: Source) -> str:
    """前端「参考来源」标签：文档名 · 最后一级章节 · 第 N 页。"""
    parts = [source.doc_name]
    if source.section:
        parts.append(source.section.split(" > ")[-1])
    if source.page:
        parts.append(f"第 {source.page} 页")
    return " · ".join(parts)


def source_refs(result: PolicySearchResult, limit: int = 4) -> list[dict[str, str]]:
    """去重后的出处（同一文档同一章节只列一次），最多 limit 条。"""
    titles = list(dict.fromkeys(source_title(s) for s in result.sources))
    return [{"title": t} for t in titles[:limit]]
