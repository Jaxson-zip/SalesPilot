"""切块（架构设计 §5.3）：800 / 120 字符，中文分隔符优先，保留标题路径；内容哈希用于去重。"""

import hashlib
import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
SEPARATORS = ["\n## ", "\n### ", "\n\n", "。", "；", "，", ""]
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chunk:
    scope: str
    pack: str | None
    doc_name: str
    section: str | None
    content: str
    page: int | None = None

    @property
    def content_hash(self) -> str:
        raw = f"{self.scope}\n{self.doc_name}\n{self.section or ''}\n{self.content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
        keep_separator="end",
        strip_whitespace=True,
    )


def split_sections(markdown: str) -> list[tuple[str | None, str]]:
    """按 #/##/### 标题拆分，返回 [(标题路径, 正文)]。标题路径形如「一级 > 二级」。"""
    sections: list[tuple[str | None, str]] = []
    path: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append((" > ".join(path) or None, text))
        buf.clear()

    for line in markdown.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = [*path[: level - 1], m.group(2)]
            continue
        buf.append(line)
    flush()
    return sections


def chunk_markdown(
    markdown: str, *, scope: str, doc_name: str, pack: str | None = None
) -> list[Chunk]:
    splitter = make_splitter()
    chunks: list[Chunk] = []
    for section, text in split_sections(markdown):
        for piece in splitter.split_text(text):
            chunks.append(
                Chunk(scope=scope, pack=pack, doc_name=doc_name, section=section, content=piece)
            )
    return chunks


def dedupe(chunks: list[Chunk], existing_hashes: set[str]) -> list[Chunk]:
    """去掉库里已有的、以及本批次内重复的块。"""
    seen = set(existing_hashes)
    fresh: list[Chunk] = []
    for chunk in chunks:
        if chunk.content_hash in seen:
            continue
        seen.add(chunk.content_hash)
        fresh.append(chunk)
    return fresh
