"""文档加载（架构设计 §5.2）：Markdown 保留标题层级；PDF 按页；Excel 每张表转成 Markdown 表格。

加载器只负责「文件 → 带元数据的块」，切块规则统一在 chunking.py
（表格整表成块、超长按行切并重复表头）。
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from pypdf import PdfReader

from app.rag.chunking import Chunk, chunk_markdown, chunk_table, chunk_text, split_sections

Loader = Callable[[Path, str, str | None], list[Chunk]]
# 句末标点：以这些结尾的行是段落结束
_SENTENCE_END = tuple("。！？；：.!?;:）)】」")
_PAGE_NO_RE = re.compile(r"^(第\s*\d+\s*页|-?\s*\d+\s*-?|\d+\s*/\s*\d+|page\s*\d+)$", re.IGNORECASE)
# 标题：「第一章 总则」→ 二级；「2.1 报价审批」→ 三级（不以句末标点结尾、不超过 30 字）
_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百\d]+[章节部分]\s*\S")
_SUBSECTION_RE = re.compile(r"^\d+(\.\d+)+\s*\S")
_MAX_HEADING = 30
# 排版折行：长度接近本页最长行的行才视为被折断，需要和下一行合并
_WRAP_RATIO = 0.85
# PDF 里常见的「康熙部首 / 部首补充」字符：NFKC 只覆盖一部分（⽰→示），其余手工映射
_RADICALS = str.maketrans({"⻚": "页", "⻅": "见", "⻓": "长", "⻔": "门", "⻢": "马", "⻆": "角"})


def _normalize_char(ch: str) -> str:
    # 只处理部首和兼容汉字区；不能整行 NFKC，否则中文全角标点（，：（）会被改成半角
    code = ord(ch)
    if 0x2E80 <= code <= 0x2FDF or 0xF900 <= code <= 0xFAFF:
        return unicodedata.normalize("NFKC", ch.translate(_RADICALS))
    return ch


def normalize_line(line: str) -> str:
    return "".join(_normalize_char(ch) for ch in line).strip()


def load_markdown(path: Path, scope: str, pack: str | None) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    return chunk_markdown(text, scope=scope, doc_name=path.stem, pack=pack)


# ---------- PDF ----------


def repeated_lines(pages: list[list[str]]) -> set[str]:
    """页眉页脚：每页首尾两行里，在半数以上页面（至少 2 页）重复出现的文字。"""
    if len(pages) < 2:
        return set()
    edges = Counter(line for lines in pages for line in {*lines[:2], *lines[-2:]})
    need = max(2, (len(pages) + 1) // 2)
    return {line for line, n in edges.items() if n >= need}


def heading_level(line: str) -> int | None:
    """章 → 2，x.y 小节 → 3；不是标题返回 None。"""
    if len(line) > _MAX_HEADING or line.endswith(_SENTENCE_END):
        return None
    if _CHAPTER_RE.match(line):
        return 2
    if _SUBSECTION_RE.match(line):
        return 3
    return None


def clean_page(lines: list[str], noise: set[str]) -> list[str]:
    """去页眉页脚和页码；标题转成 Markdown 标题；只把排版折断的长行和下一行合并。"""
    kept = [ln for ln in lines if ln not in noise and not _PAGE_NO_RE.match(ln)]
    widest = max((len(ln) for ln in kept), default=0)
    out: list[str] = []
    pending = ""
    for line in kept:
        level = heading_level(line) if not pending else None
        if level:
            out.append(f"{'#' * level} {line}")
            continue
        pending += line
        wrapped = len(line) >= widest * _WRAP_RATIO and not line.endswith(_SENTENCE_END)
        if not wrapped:
            out.append(pending)
            pending = ""
    if pending:
        out.append(pending)
    return out


def pdf_pages(path: Path) -> list[list[str]]:
    """每页清洗后的行（页码从 1 开始，对应列表下标 + 1）。"""
    reader = PdfReader(str(path))
    raw = [
        [normalize_line(ln) for ln in (page.extract_text() or "").splitlines() if ln.strip()]
        for page in reader.pages
    ]
    noise = repeated_lines(raw)
    return [clean_page(lines, noise) for lines in raw]


def load_pdf(path: Path, scope: str, pack: str | None) -> list[Chunk]:
    """按页切块，块带页码；标题路径跨页延续（某页开头不是标题时沿用上一页的章节）。"""
    chunks: list[Chunk] = []
    carried: list[str] = []
    for no, lines in enumerate(pdf_pages(path), start=1):
        text = "\n".join([*carried, *lines])
        for section, body in split_sections(text):
            chunks.extend(
                Chunk(
                    scope=scope, pack=pack, doc_name=path.stem, section=section, content=p, page=no
                )
                for p in chunk_text(body)
            )
        headings = [ln for ln in [*carried, *lines] if ln.startswith("#")]
        carried = _open_headings(headings)
    return chunks


def _open_headings(headings: list[str]) -> list[str]:
    """到本页结束时仍然「打开」的标题链（每一级保留最后一个）。"""
    by_level: dict[int, str] = {}
    for h in headings:
        level = len(h) - len(h.lstrip("#"))
        by_level = {k: v for k, v in by_level.items() if k < level} | {level: h}
    return [by_level[k] for k in sorted(by_level)]


# ---------- Excel ----------


def _cell(value: Any) -> str:
    if value is None:
        return ""
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return text.replace("|", "／").replace("\n", " ").strip()


def rows_to_markdown(rows: list[list[Any]]) -> str:
    """二维表 → Markdown 表格（第一行作表头，去掉全空的行和列）。"""
    cells = [[_cell(v) for v in row] for row in rows]
    cells = [row for row in cells if any(row)]
    if not cells:
        return ""
    width = max(len(row) for row in cells)
    cells = [row + [""] * (width - len(row)) for row in cells]
    used = [i for i in range(width) if any(row[i] for row in cells)]
    cells = [[row[i] for i in used] for row in cells]
    head, *body = cells
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)


def load_excel(path: Path, scope: str, pack: str | None) -> list[Chunk]:
    """每张工作表一张表，section 为工作表名；超长按行切并重复表头。"""
    workbook = load_workbook(path, read_only=True, data_only=True)
    chunks: list[Chunk] = []
    try:
        for sheet in workbook.worksheets:
            table = rows_to_markdown([list(r) for r in sheet.iter_rows(values_only=True)])
            if not table:
                continue
            chunks.extend(
                Chunk(scope=scope, pack=pack, doc_name=path.stem, section=sheet.title, content=p)
                for p in chunk_table(table)
            )
    finally:
        workbook.close()
    return chunks


LOADERS: dict[str, Loader] = {".md": load_markdown, ".pdf": load_pdf, ".xlsx": load_excel}


def load_file(path: Path, scope: str, pack: str | None) -> list[Chunk]:
    loader = LOADERS.get(path.suffix.lower())
    return loader(path, scope, pack) if loader else []


def supported_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in LOADERS and p.is_file())
