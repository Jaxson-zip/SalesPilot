"""检索后重排：按相关度调整顺序并取前 4；重排不可用时保持向量顺序，不影响回答。"""

import pytest

from app.common.errors import BizError, ErrorCode
from app.rag import retriever
from app.rag.retriever import Source, rerank_hits


def _hits(n: int) -> list[Source]:
    return [
        Source(content=f"片段{i}", doc_name="D", section=str(i), score=0.9 - i * 0.05)
        for i in range(n)
    ]


def test_rerank_reorders_and_keeps_top4(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str], int | None]] = []

    def fake(
        query: str, docs: list[str], *, top_n: int | None = None, **_: object
    ) -> list[tuple[int, float]]:
        calls.append((query, docs, top_n))
        return [(5, 0.95), (2, 0.8), (0, 0.6), (7, 0.4)]

    monkeypatch.setattr(retriever, "rerank_texts", fake)
    out = rerank_hits("招待标准", _hits(8))
    assert [h.section for h in out] == ["5", "2", "0", "7"]
    assert out[0].rerank_score == 0.95 and out[0].score == pytest.approx(0.65)  # 向量分数保留
    assert calls == [("招待标准", [f"片段{i}" for i in range(8)], 4)]


def test_rerank_failure_keeps_vector_order(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> list[tuple[int, float]]:
        raise BizError(ErrorCode.UPSTREAM, "rerank 502")

    monkeypatch.setattr(retriever, "rerank_texts", boom)
    out = rerank_hits("q", _hits(6))
    assert [h.section for h in out] == ["0", "1", "2", "3"] and out[0].rerank_score is None


def test_single_hit_skips_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    def never(*_a: object, **_k: object) -> list[tuple[int, float]]:
        raise AssertionError("只有一条时不需要重排")

    monkeypatch.setattr(retriever, "rerank_texts", never)
    assert len(rerank_hits("q", _hits(1))) == 1
