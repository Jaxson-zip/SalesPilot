"""上传 / 导入的异常文件：一律返回明确的 40001，不出 500。

回归：试用报告里异常 DOCX 和超长预算的 CSV 触发了 500。
"""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent import materials
from app.crm.services.customer_import import _money
from tests.api.conftest import ADMIN_H, SALES_H

DOC_XML = (
    b"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
    b"<w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body></w:document>"
)


def _docx(xml: bytes = DOC_XML) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def _patched_central(flag_offset: int, value: int, *, bit_or: bool = False) -> bytes:
    raw = bytearray(_docx())
    at = raw.find(b"PK\x01\x02") + flag_offset
    raw[at] = raw[at] | value if bit_or else value
    return bytes(raw)


def _material(client: TestClient, name: str, data: bytes) -> dict:
    r = client.post("/api/agent/materials", files={"file": (name, data)}, headers=SALES_H)
    return {"status": r.status_code, **r.json()}


@pytest.mark.parametrize(
    "data",
    [
        _patched_central(10, 99),  # 不支持的压缩方式（曾 NotImplementedError → 500）
        _patched_central(8, 1, bit_or=True),  # 标记为加密（曾 RuntimeError → 500）
        _docx(b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'aaaa'>]><x>&a;</x>"),  # DTD 实体
        # XML 声明了不存在的编码（曾 LookupError → 500）
        _docx(b"<?xml version='1.0' encoding='xyz-unknown'?><a/>"),
        _docx(b"<?xml version='1.0' encoding='utf-32'?><a/>"),  # 编码与内容不符
        b"\x00\x01 not a zip",
        b"PK\x05\x06" + b"\x00" * 18,  # 空压缩包
    ],
    ids=[
        "unsupported-compression",
        "encrypted",
        "dtd-entity",
        "unknown-xml-encoding",
        "mismatched-xml-encoding",
        "garbage",
        "empty-zip",
    ],
)
def test_bad_docx_is_validation_error(client: TestClient, data: bytes) -> None:
    res = _material(client, "坏文件.docx", data)
    assert res["status"] == 400 and res["code"] == 40001, res


def test_docx_too_large_after_unzip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """压缩炸弹：按压缩包头里的解压大小拒绝，不先解出来再判断。"""
    monkeypatch.setattr(materials, "MAX_DOCX_XML", 100)
    res = _material(client, "大.docx", _docx(DOC_XML + b" " * 200))
    assert res["status"] == 400 and "太大" in res["message"]


def test_good_docx_still_works(client: TestClient) -> None:
    res = _material(client, "正常.docx", _docx())
    assert res["code"] == 0 and res["data"]["text"] == "hello"


@pytest.mark.parametrize("name", ["假图.png", "假图.jpg", "假图.webp"])
def test_fake_image_rejected_before_model(client: TestClient, name: str) -> None:
    """扩展名是图片、内容不是：直接 40001，不调视觉模型（曾返回 502「识别失败」）。"""
    res = _material(client, name, b"not an image at all")
    assert res["status"] == 400 and "图片文件无法识别" in res["message"]
    r = client.post("/api/agent/samples", files={"file": (name, b"nope")}, headers=SALES_H)
    assert r.status_code == 400 and "图片文件无法识别" in r.json()["message"]


def test_money_parsing_limits() -> None:
    assert _money("5万") == 5_000_000
    assert _money("1,200.5") == 120_050
    assert _money("abc") == -1
    assert _money("9" * 400) == -2  # 曾 float 溢出 → 500
    assert _money("100000000000000000000") == -2  # 超出 BIGINT
    assert _money("20000000000") == -2  # 超过 100 亿元
    assert _money("10000000000") == 1_000_000_000_000  # 正好 100 亿元


def _preview(client: TestClient, text: str) -> dict:
    files = {"file": ("customers.csv", text.encode("utf-8"), "text/csv")}
    r = client.post("/api/customers/import/preview", files=files, headers=SALES_H)
    return {"status": r.status_code, **r.json()}


@pytest.mark.parametrize(
    ("budget", "expect"),
    [
        ("9" * 400, "不能超过 100 亿元"),
        ("100000000000000000000", "不能超过 100 亿元"),
        ("20000000000", "不能超过 100 亿元"),
        ("99999999万", "不能超过 100 亿元"),
    ],
)
def test_import_preview_rejects_oversized_budget(
    client: TestClient, budget: str, expect: str
) -> None:
    res = _preview(client, f"客户名称,年度预算（元）\n预算校验测试有限公司,{budget}\n")
    assert res["status"] == 200, res
    row = res["data"]["rows"][0]
    assert row["status"] == "error" and expect in row["message"]
    assert res["data"]["ok"] == 0


def test_import_rejects_nul_and_overlong_field(client: TestClient) -> None:
    res = _preview(client, "客户名称,行业\n控制字符\x00测试公司,制造\n")
    assert res["data"]["rows"][0]["status"] == "error"
    assert "控制字符" in res["data"]["rows"][0]["message"]
    long_cell = "客户名称,行业\n超长测试公司," + "x" * 200_000 + "\n"
    res = _preview(client, long_cell)
    assert res["status"] == 400 and res["code"] == 40001 and "CSV 格式有误" in res["message"]


@pytest.mark.parametrize("data", [b"PK\x03\x04garbage", _docx()], ids=["garbage", "docx-as-xlsx"])
def test_bad_xlsx_is_validation_error(client: TestClient, data: bytes) -> None:
    files = {"file": ("customers.xlsx", data, "application/vnd.ms-excel")}
    r = client.post("/api/customers/import/preview", files=files, headers=SALES_H)
    assert r.status_code == 400 and r.json()["code"] == 40001


def test_corrupt_knowledge_pdf_is_validation_error(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """知识库上传损坏的 PDF：是文件的问题 → 40001，且不把原始异常文字回给页面。"""
    from app.crm.services import settings_service

    monkeypatch.setattr(settings_service, "uploaded_dir", lambda pack: tmp_path / pack)
    files = {"file": ("损坏.pdf", b"%PDF-1.4 garbage", "application/pdf")}
    r = client.post("/api/packs/it_office/knowledge", files=files, headers=ADMIN_H).json()
    assert r["code"] == 40001 and "无法读取" in r["message"]


def test_nul_character_is_validation_error_everywhere(client: TestClient) -> None:
    """回归：名称、搜索词里带 NUL（\\x00）时数据库拒收，曾统一返回 500。"""
    r = client.post("/api/customers", json={"name": "控制\x00字符"}, headers=SALES_H)
    assert r.status_code == 400 and r.json()["code"] == 40001
    assert "控制字符" in r.json()["message"]
    for path in ("/api/customers", "/api/opportunities", "/api/quotes"):
        r = client.get(path, params={"q": "a\x00b"}, headers=SALES_H)
        assert r.status_code == 400 and r.json()["code"] == 40001, (path, r.text)
