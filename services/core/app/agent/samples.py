"""客户样例图片 → 单据类型、字段名、清晰度，汇总后交给出方案流程。

- 一次识别一张（前端并发上传、显示进度、单张失败可重试），走视觉模型（网关别名 VISION_MODEL）；
- 只要类型和字段名，不要字段值；原图和识别结果都不入库，汇总结果随需求清单保存到商机；
- 发送时前端把逐张结果带上，这里汇总成 SampleSummary，并整理成一段文字交给需求抽取。
"""

import base64
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, field_validator

from app.agent.materials import (
    IMAGE_TYPES,
    MATERIAL_OPEN,
    MAX_BYTES,
    VISION_MODEL,
    check_image,
)
from app.common.errors import BizError, ErrorCode
from app.llm.client import get_chat_model, model_available
from app.packs.base import SampleSummary, SampleType

logger = logging.getLogger("core.agent")

MAX_SAMPLES = 30
MAX_FIELDS = 30
TYPE_FIELDS = 20  # 汇总时每类单据最多列出的字段数

SAMPLE_PROMPT = (
    "这是客户提供的业务单据 / 表单样例图片，用来评估要做的识别系统。"
    "只输出一个 JSON 对象，不要其他文字：\n"
    '{"doc_type": "单据类型，例如 增值税发票、装箱单、提单、手写收据；看不出来写 其他",'
    ' "fields": ["需要录入系统的字段名，例如 发票号码、开票日期、金额；'
    '只写字段名，不写字段值，最多 30 个"],'
    ' "quality": "clear 清晰 / blurry 模糊、反光或倾斜严重 / handwritten 主要内容是手写"}'
)

Quality = Literal["clear", "blurry", "handwritten"]


class SampleItem(BaseModel):
    """一张样例图片的识别结果。"""

    name: str = Field(min_length=1, max_length=120)
    doc_type: str = Field(min_length=1, max_length=30)
    fields: list[str] = Field(max_length=MAX_FIELDS)
    quality: Quality

    @field_validator("fields")
    @classmethod
    def _clean_fields(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for f in v:
            f = str(f).strip()[:30]
            if f and f not in out:
                out.append(f)
        return out


class SamplesIn(BaseModel):
    """随聊天消息发送的样例识别结果（失败的不带，total 是上传的张数）。"""

    total: int = Field(ge=1, le=MAX_SAMPLES)
    items: list[SampleItem] = Field(min_length=1, max_length=MAX_SAMPLES)


def _invalid(msg: str) -> BizError:
    return BizError(ErrorCode.VALIDATION, msg, {"errors": [{"loc": ["body", "file"], "msg": msg}]})


def parse_reply(name: str, text: str) -> SampleItem:
    """解析视觉模型的回复：取第一个 JSON 对象，字段缺失或不合法时按「其他 / 清晰」兜底。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no json in reply")
    data = json.loads(m.group(0))
    fields = data.get("fields")
    quality = data.get("quality")
    return SampleItem(
        name=name,
        doc_type=(str(data.get("doc_type") or "").strip() or "其他")[:30],
        fields=[str(f) for f in fields][:MAX_FIELDS] if isinstance(fields, list) else [],
        quality=quality if quality in ("clear", "blurry", "handwritten") else "clear",
    )


def analyze(file_name: str, content: bytes, request_id: str | None = None) -> SampleItem:
    name = Path(file_name or "样例").name[:120]
    mime = IMAGE_TYPES.get(Path(name).suffix.lower())
    if not mime:
        raise _invalid("样例只支持图片（.png / .jpg / .webp）")
    if not content:
        raise _invalid("文件为空")
    if len(content) > MAX_BYTES:
        raise _invalid("图片不能超过 10 MB")
    check_image(content, mime)
    if not model_available(VISION_MODEL, request_id):
        raise BizError(ErrorCode.MODEL_CAPABILITY, "图片识别模型未配置，暂时不能分析样例图片")
    url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
    llm = get_chat_model(VISION_MODEL, temperature=0, streaming=False, request_id=request_id)
    message = HumanMessage(
        content=[
            {"type": "text", "text": SAMPLE_PROMPT},
            {"type": "image_url", "image_url": {"url": url}},
        ]
    )
    try:
        out = llm.invoke([message])
    except Exception as exc:
        logger.warning("sample analyze failed", exc_info=True)
        raise BizError(ErrorCode.UPSTREAM, "图片识别失败，请稍后重试") from exc
    try:
        return parse_reply(name, out.content if isinstance(out.content, str) else "")
    except (ValueError, TypeError):
        logger.warning("sample reply not json: %.200s", out.content)
        raise BizError(ErrorCode.UPSTREAM, "没能识别这张图片，请换一张更清晰的重试") from None


def summarize(samples: SamplesIn) -> SampleSummary:
    """按单据类型分组：张数、字段（按出现次数排序），以及模糊、手写的张数。"""
    groups: dict[str, list[SampleItem]] = {}
    for item in samples.items:
        groups.setdefault(item.doc_type, []).append(item)
    types = []
    for name, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        counts = Counter(f for it in items for f in it.fields)
        order = {f: i for i, f in enumerate(f for it in items for f in it.fields)}
        fields = sorted(counts, key=lambda f: (-counts[f], order[f]))[:TYPE_FIELDS]
        types.append(SampleType(name=name, count=len(items), fields=fields))
    quality = Counter(it.quality for it in samples.items)
    return SampleSummary(
        total=max(samples.total, len(samples.items)),
        analyzed=len(samples.items),
        types=types,
        blurry=quality["blurry"],
        handwritten=quality["handwritten"],
    )


def describe(s: SampleSummary) -> str:
    """给需求抽取的文字说明（也是用户消息里的材料正文）。"""
    head = f"客户提供了 {s.total} 张样例图片，识别了 {s.analyzed} 张，共 {len(s.types)} 类单据："
    lines = [head]
    for t in s.types:
        fields = "、".join(t.fields) or "（没识别出字段）"
        lines.append(f"- {t.name} {t.count} 张，字段：{fields}")
    if s.blurry or s.handwritten:
        lines.append(f"其中模糊 {s.blurry} 张、手写 {s.handwritten} 张。")
    return "\n".join(lines)


def label(s: SampleSummary) -> str:
    return f"客户样例图片（{s.total} 张 · {len(s.types)} 类单据）"


def compose(message: str, s: SampleSummary) -> str:
    """用户消息 + 样例汇总：沿用材料的标记，历史记录里只显示用户的话。"""
    return f'{message}\n\n{MATERIAL_OPEN} name="{label(s)}">\n{describe(s)}\n</material>'
