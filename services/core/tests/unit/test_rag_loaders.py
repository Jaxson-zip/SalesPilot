"""多格式加载与表格切块（架构设计 §5.2 / §5.3）：Markdown / PDF / Excel。"""

from pathlib import Path

from openpyxl import Workbook

from app.rag.chunking import chunk_markdown, chunk_table, split_blocks, split_sections
from app.rag.ingest import load_chunks
from app.rag.loaders import (
    clean_page,
    heading_level,
    load_file,
    normalize_line,
    repeated_lines,
    rows_to_markdown,
)

CORE = Path(__file__).resolve().parents[2]
CONTRACT_PDF = CORE / "seed" / "knowledge" / "company" / "合同审批与回款流程.pdf"
GPU_XLSX = CORE / "app" / "packs" / "llm_deploy" / "knowledge" / "GPU与整机参数表.xlsx"


# ---------- 表格 ----------


def _table(rows: int) -> str:
    lines = ["| 型号 | 说明 |", "|---|---|"]
    lines += [f"| M{i:03d} | {'参数说明' * 8} |" for i in range(rows)]
    return "\n".join(lines)


def test_small_table_is_one_chunk() -> None:
    assert chunk_table(_table(3)) == [_table(3)]


def test_long_table_split_by_rows_with_header_repeated() -> None:
    pieces = chunk_table(_table(60), max_chars=800)
    assert len(pieces) > 1
    for piece in pieces:
        assert piece.startswith("| 型号 | 说明 |\n|---|---|\n")
        assert len(piece) <= 800
    rows = [ln for p in pieces for ln in p.splitlines()[2:]]
    assert len(rows) == 60  # 没有丢行，也没有重复的数据行


def test_markdown_table_not_cut_by_text_splitter() -> None:
    text = "说明文字。\n\n" + _table(5) + "\n\n后续说明。"
    assert [t for t, _ in split_blocks(text)] == [False, True, False]
    chunks = chunk_markdown(f"# 文档\n## 参数\n{text}", scope="company", doc_name="d")
    assert any(c.content == _table(5) for c in chunks)


def test_sections_without_top_level_heading() -> None:
    """回归：PDF 从二级标题开始时，同级标题之间不能互相嵌套。"""
    md = "## 第一章 总则\n甲\n## 第二章 权限\n### 2.1 报价\n乙\n## 第三章 回款\n丙"
    assert [s for s, _ in split_sections(md)] == [
        "第一章 总则",
        "第二章 权限 > 2.1 报价",
        "第三章 回款",
    ]


# ---------- PDF ----------


def test_normalize_radicals_but_keep_fullwidth_punctuation() -> None:
    """回归：整行 NFKC 会把中文全角标点改成半角。"""
    assert normalize_line("演⽰公司 第 1 ⻚") == "演示公司 第 1 页"
    assert normalize_line("合同金额，审批人：（主管）") == "合同金额，审批人：（主管）"


def test_heading_level() -> None:
    assert heading_level("第二章 审批权限") == 2
    assert heading_level("2.1 报价审批") == 3
    assert heading_level("2.3 非标准条款无论金额大小，均需财务负责人审批。") is None
    assert heading_level("合同金额 审批人 说明") is None


def test_repeated_header_footer_detected_on_two_pages() -> None:
    pages = [["正文一", "某某公司 内部制度", "第 1 页"], ["正文二", "某某公司 内部制度", "第 2 页"]]
    assert repeated_lines(pages) == {"某某公司 内部制度"}


def test_clean_page_merges_only_wrapped_lines() -> None:
    long_line = "这是一段很长的正文被排版折断了没有句末标点" * 2
    lines = [long_line, "接着上一行写完。", "表头 审批人 说明", "第 3 页"]
    out = clean_page(lines, set())
    assert out == [long_line + "接着上一行写完。", "表头 审批人 说明"]


def test_real_pdf_pages_sections_and_noise_removed() -> None:
    chunks = load_file(CONTRACT_PDF, "company", None)
    assert {c.page for c in chunks} == {1, 2}
    text = "\n".join(c.content for c in chunks)
    assert "内部制度\n" not in text and "第 1 页" not in text  # 页眉页脚已去掉
    approval = next(c for c in chunks if c.section == "第二章 审批权限 > 2.2 合同审批")
    assert "200 万元以上" in approval.content and approval.page == 1
    payment = next(c for c in chunks if c.section and "3.1" in c.section)
    assert payment.page == 2 and "预付 30%" in payment.content


# ---------- Excel ----------


def test_rows_to_markdown_skips_empty_rows_and_columns() -> None:
    rows = [["型号", None, "显存"], [None, None, None], ["L20", None, 48.0], ["H20", None, "96|GB"]]
    assert rows_to_markdown(rows) == "\n".join(
        ["| 型号 | 显存 |", "|---|---|", "| L20 | 48 |", "| H20 | 96／GB |"]
    )


def test_excel_each_sheet_is_a_table(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "报价"
    ws.append(["项目", "数量"])
    ws.append(["部署实施", 1])
    wb.create_sheet("空表")
    path = tmp_path / "示例.xlsx"
    wb.save(path)
    chunks = load_file(path, "company", None)
    assert [(c.section, c.doc_name) for c in chunks] == [("报价", "示例")]
    assert chunks[0].content.startswith("| 项目 | 数量 |")


def test_real_excel_and_scope_loading() -> None:
    sections = {c.section for c in load_file(GPU_XLSX, "pack:llm_deploy", "llm_deploy")}
    assert sections == {"GPU 卡", "整机配置", "选型问答"}
    pack = load_chunks("pack:llm_deploy")
    assert {"GPU与整机参数表", "显存估算参考表"} <= {c.doc_name for c in pack}
    company = load_chunks("company")
    assert "合同审批与回款流程" in {c.doc_name for c in company}


def test_unsupported_file_ignored(tmp_path: Path) -> None:
    path = tmp_path / "说明.docx"
    path.write_bytes(b"x")
    assert load_file(path, "company", None) == []


def test_embedding_text_prefixes_title_path() -> None:
    from app.rag.chunking import Chunk, embedding_text

    c = Chunk(
        scope="company",
        pack=None,
        doc_name="费用报销管理制度",
        section="4 客户招待 > 4.2 招待标准",
        content="人均 150 元",
    )
    assert embedding_text(c) == "费用报销管理制度 > 4 客户招待 > 4.2 招待标准\n人均 150 元"
    bare = Chunk(scope="company", pack=None, doc_name="说明", section=None, content="正文")
    assert embedding_text(bare) == "说明\n正文"
