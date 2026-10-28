"""知识库入库：每批不超过通义 Embedding 的上限（10 条）；--reset 换模型后能整体重建。

Embedding 用假函数代替（只记录批次大小），事务最后回滚，不改动测试库。
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.common.db import get_engine
from app.crm.models import KbChunk
from app.rag import ingest


@pytest.fixture
def db(db_available: bool) -> Iterator[Session]:
    if not db_available:
        pytest.skip("测试数据库不可用")
    with Session(get_engine()) as session:
        yield session
        session.rollback()


def test_ingest_batches_and_reset(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    batches: list[int] = []
    dims = get_settings().embedding_dims

    def fake_embed(texts: list[str], **_: object) -> list[list[float]]:
        batches.append(len(texts))
        return [[0.1] * dims for _ in texts]

    monkeypatch.setattr(ingest, "embed_texts", fake_embed)
    count = lambda: db.scalar(  # noqa: E731
        select(func.count()).select_from(KbChunk).where(KbChunk.scope == "company")
    )

    first = ingest.ingest_scope(db, "company", reset=True)
    assert first > 10 and count() == first
    assert batches and max(batches) <= 10  # 通义 Embedding 每次最多 10 条

    assert ingest.ingest_scope(db, "company") == 0  # 内容没变：按哈希去重，不重复调用
    assert ingest.ingest_scope(db, "company", reset=True) == first  # 换模型：清空后全部重建
    assert count() == first
