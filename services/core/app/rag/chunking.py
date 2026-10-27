"""切块（架构设计 §5.3）：800 / 120 字符，中文分隔符优先，保留标题路径；内容哈希用于去重。

表格单独处理：整张表作为一块；超长时按行切开，每块都重复表头，避免价格表、参数表被切碎后
只剩数字、看不出是哪一列。
"""

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
    # (级别, 标题) 栈：遇到同级或更高级的标题先弹出。
    # 文档不一定从一级标题开始（PDF 常从「第一章」开始），不能按级别下标截断
    # 回归：曾得到「第一章 总则 > 第二章 审批权限」这样的错误路径
    path: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append((" > ".join(t for _, t in path) or None, text))
        buf.clear()

    for line in markdown.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, m.group(2)))
            continue
        buf.append(line)
    flush()
    return sections


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def split_blocks(text: str) -> list[tuple[bool, str]]:
    """把一节正文拆成 [(是否表格, 文本)]，连续的「|」行算一张表。"""
    blocks: list[tuple[bool, list[str]]] = []
    for line in text.splitlines():
        is_table = _is_table_line(line)
        if blocks and blocks[-1][0] == is_table:
            blocks[-1][1].append(line)
        else:
            blocks.append((is_table, [line]))
    joined = [(t, "\n".join(lines).strip()) for t, lines in blocks]
    return [(t, text) for t, text in joined if text]


def chunk_table(table: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """整表一块；超长时按行切，每块重复表头（表头行 + 分隔行）。"""
    lines = [ln for ln in table.splitlines() if ln.strip()]
    if len(table) <= max_chars or len(lines) <= 3:
        return [table]
    has_sep = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= set("-: ")
    head = lines[:2] if has_sep else lines[:1]
    rows = lines[len(head) :]
    pieces: list[str] = []
    current: list[str] = []
    for row in rows:
        candidate = "\n".join([*head, *current, row])
        if current and len(candidate) > max_chars:
            pieces.append("\n".join([*head, *current]))
            current = []
        current.append(row)
    if current:
        pieces.append("\n".join([*head, *current]))
    return pieces


def chunk_text(text: str) -> list[str]:
    """正文用递归分隔符切，表格按 chunk_table 处理。"""
    splitter = make_splitter()
    pieces: list[str] = []
    for is_table, block in split_blocks(text):
        pieces.extend(chunk_table(block) if is_table else splitter.split_text(block))
    return pieces


def chunk_markdown(
    markdown: str, *, scope: str, doc_name: str, pack: str | None = None
) -> list[Chunk]:
    return [
        Chunk(scope=scope, pack=pack, doc_name=doc_name, section=section, content=piece)
        for section, text in split_sections(markdown)
        for piece in chunk_text(text)
    ]


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


def embedding_text(chunk: Chunk) -> str:
    """向量化用的文本：在正文前加「文档名 > 章节」。

    制度条款往往很短（「客户招待按人均 150 元执行」），章节标题本身就是重要语义；
    只改向量化输入，入库和展示的 content 不变。
    """
    title = " > ".join(p for p in (chunk.doc_name, chunk.section) if p)
    return f"{title}\n{chunk.content}"
