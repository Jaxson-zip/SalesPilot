"""一手材料：会议纪要、聊天记录、名片 / 截图 → 纯文本，交给 AI 整理成跟进、联系人和下一步。

- 文本类（.txt / .md / .csv）、Word（.docx）、PDF 本地解析，不经过大模型；
- 图片（截图、名片、白板照片）交给视觉模型识别文字（网关别名 VISION_MODEL）；
  没配 Key 时提示用户直接粘贴文字；
- 材料不入库：文字随这一轮消息发给 Agent，用户确认后才写入跟进 / 联系人 / 任务。
"""

import base64
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.common.errors import BizError, ErrorCode
from app.llm.client import get_chat_model, model_available

logger = logging.getLogger("core.agent")

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 12_000
VISION_MODEL = "qwen-vl"
TEXT_SUFFIXES = {".txt", ".md", ".csv"}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
SUPPORTED = "支持文本（.txt / .md）、Word（.docx）、PDF 和图片（.png / .jpg）"

# 消息里材料的分隔标记：history 按它把材料原文从用户气泡里去掉
MATERIAL_OPEN = "<material"
MaterialKind = Literal["text", "docx", "pdf", "image"]

VISION_PROMPT = (
    "把图片里的文字原样整理出来（聊天截图按「发言人：内容」逐条列出，名片列出姓名、公司、职务、电话、"
    "邮箱）。只输出图片里的内容，不要总结，不要补充图片里没有的信息。"
)


class MaterialOut(BaseModel):
    name: str
    kind: MaterialKind
    text: str
    chars: int  # 原文字数（截断前）
    truncated: bool


class MaterialIn(BaseModel):
    """随聊天消息一起发送的材料（前端从 /materials 拿到的文字，用户可以不改直接发）。"""

    name: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=MAX_CHARS)


def _invalid(msg: str) -> BizError:
    return BizError(ErrorCode.VALIDATION, msg, {"errors": [{"loc": ["body", "file"], "msg": msg}]})


def _clean(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise _invalid("文本文件编码无法识别，请另存为 UTF-8")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# 解压后的正文上限：10 MB 的压缩包可以解出几百 MB（压缩炸弹），先看头里的大小再读
MAX_DOCX_XML = 30 * 1024 * 1024
DOCX_BAD = "Word 文件无法读取（可能已损坏或加密），请另存为 .docx 后重试"


def _document_xml(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > MAX_DOCX_XML:
            raise _invalid("Word 文件内容太大，请拆分后上传")
        xml = z.read(info)
    # 正常的 .docx 没有 DTD；有就可能是实体膨胀攻击
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise _invalid(DOCX_BAD)
    return xml


def docx_text(content: bytes) -> str:
    """不依赖 python-docx：直接读 word/document.xml 的段落和表格文字。"""
    # 上传的文件什么样都可能有：加密（RuntimeError）、不支持的压缩方式（NotImplementedError）、
    # XML 声明了不存在的编码（LookupError）……逐个列举已漏过两次，
    # 所以解析阶段的任何异常都按文件不合法处理
    try:
        root = ElementTree.fromstring(_document_xml(content))
    except BizError:
        raise
    except Exception as exc:
        logger.info("docx unreadable: %s", type(exc).__name__)
        raise _invalid(DOCX_BAD) from exc
    paras = []
    for p in root.iter(f"{_W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{_W}t"))
        if text.strip():
            paras.append(text)
    return "\n".join(paras)


def pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise _invalid("PDF 无法读取（可能已加密或损坏）") from exc


def _looks_like(content: bytes, mime: str) -> bool:
    if mime == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def check_image(content: bytes, mime: str) -> None:
    """扩展名是图片但内容不是：不送给视觉模型（白花一次调用，还会报「识别失败」）。"""
    if not _looks_like(content, mime):
        raise _invalid("图片文件无法识别，请上传 png、jpg 或 webp 图片")


def image_text(content: bytes, mime: str, request_id: str | None = None) -> str:
    check_image(content, mime)
    if not model_available(VISION_MODEL, request_id):
        raise BizError(
            ErrorCode.MODEL_CAPABILITY, "图片识别模型未配置，请把截图里的文字直接粘贴到输入框"
        )
    url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
    llm = get_chat_model(VISION_MODEL, temperature=0, streaming=False, request_id=request_id)
    message = HumanMessage(
        content=[
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": url}},
        ]
    )
    try:
        out = llm.invoke([message])
    except Exception as exc:
        logger.warning("vision extract failed", exc_info=True)
        raise BizError(ErrorCode.UPSTREAM, "图片识别失败，请稍后重试或直接粘贴文字") from exc
    return out.content if isinstance(out.content, str) else ""


def extract(file_name: str, content: bytes, request_id: str | None = None) -> MaterialOut:
    name = Path(file_name or "材料").name[:120]
    suffix = Path(name).suffix.lower()
    if not content:
        raise _invalid("文件为空")
    if len(content) > MAX_BYTES:
        raise _invalid("文件不能超过 10 MB")
    kind: MaterialKind
    if suffix in TEXT_SUFFIXES:
        kind, raw = "text", _decode(content)
    elif suffix == ".docx":
        kind, raw = "docx", docx_text(content)
    elif suffix == ".pdf":
        kind, raw = "pdf", pdf_text(content)
    elif suffix in IMAGE_TYPES:
        kind, raw = "image", image_text(content, IMAGE_TYPES[suffix], request_id)
    else:
        raise _invalid(SUPPORTED)
    text = _clean(raw)
    if not text:
        raise _invalid("没有读到文字（扫描版 PDF 请截图后上传）")
    return MaterialOut(
        name=name,
        kind=kind,
        text=text[:MAX_CHARS],
        chars=len(text),
        truncated=len(text) > MAX_CHARS,
    )


def compose(message: str, material: MaterialIn) -> str:
    """发给模型的用户消息：用户的话 + 材料原文（用标记包起来，提示模型材料只是数据）。"""
    body = material.text.replace("</material>", "")
    return f'{message}\n\n<material name="{material.name}">\n{body}\n</material>'


def strip(text: str) -> str:
    """历史记录里只显示用户的话，材料原文不进气泡。"""
    i = text.find(f"\n\n{MATERIAL_OPEN}")
    return text[:i] if i >= 0 else text
