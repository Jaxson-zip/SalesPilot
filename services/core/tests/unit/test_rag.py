"""RAG：切块、标题路径、去重、阈值过滤、scope。"""

from app.rag.chunking import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    Chunk,
    chunk_markdown,
    dedupe,
    split_sections,
)
from app.rag.ingest import COMPANY_DIR, load_chunks, source_dirs
from app.rag.retriever import Source, filter_hits, scopes_for

DOC = """# 费用报销管理制度
## 4 客户招待
### 4.2 招待标准
客户招待按人均 150 元执行。
## 5 附则
本制度由财务部负责解释。
"""


def test_split_sections_keeps_heading_path() -> None:
    sections = split_sections(DOC)
    assert sections[0] == (
        "费用报销管理制度 > 4 客户招待 > 4.2 招待标准",
        "客户招待按人均 150 元执行。",
    )
    assert sections[1][0] == "费用报销管理制度 > 5 附则"


def test_long_text_split_with_overlap() -> None:
    sentence = "客户招待按人均一百五十元执行，超出部分需要主管审批。"
    text = "## 长条款\n" + sentence * 100
    chunks = chunk_markdown(text, scope="company", doc_name="d")
    assert len(chunks) > 1
    assert all(len(c.content) <= CHUNK_SIZE for c in chunks)
    tail = chunks[0].content[-CHUNK_OVERLAP // 2 :]
    assert tail in chunks[1].content  # 相邻块有重叠
    assert all(c.section == "长条款" for c in chunks)


def test_chinese_separator_preferred() -> None:
    text = "甲" * 500 + "。" + "乙" * 500
    chunks = chunk_markdown(text, scope="company", doc_name="d")
    assert chunks[0].content.endswith("。")


def test_hash_dedupe() -> None:
    a = Chunk(scope="company", pack=None, doc_name="d", section=None, content="x")
    b = Chunk(scope="company", pack=None, doc_name="d", section=None, content="x")
    c = Chunk(scope="company", pack=None, doc_name="d", section=None, content="y")
    assert a.content_hash == b.content_hash != c.content_hash
    assert dedupe([a, b, c], set()) == [a, c]
    assert dedupe([a, b, c], {c.content_hash}) == [a]


def test_threshold_filter() -> None:
    hits = [
        Source(content="a", doc_name="d", section=None, score=0.4),
        Source(content="b", doc_name="d", section=None, score=0.8),
        Source(content="c", doc_name="d", section=None, score=0.5),
    ]
    result = filter_hits(hits)
    assert result.found and [s.content for s in result.sources] == ["b", "c"]
    assert filter_hits(hits[:1]).found is False


def test_scopes() -> None:
    assert scopes_for(None) == ["company"]
    assert scopes_for("llm_deploy") == ["company", "pack:llm_deploy"]


def test_load_real_documents() -> None:
    assert COMPANY_DIR.exists()
    assert {"company", "pack:llm_deploy", "pack:it_office"} <= set(source_dirs())
    chunks = load_chunks("company")
    assert any("150 元" in c.content and c.section and "4.2" in c.section for c in chunks)
    assert all(c.scope == "company" and c.pack is None for c in chunks)
