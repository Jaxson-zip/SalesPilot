"""客户样例图片：逐张识别结果的解析、汇总，以及软件外包按样例调整需求。"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import samples as sample_lib
from app.agent import service
from app.agent.materials import strip
from app.agent.nodes.requirement_fields import optional_model
from app.agent.samples import SampleItem, SamplesIn, parse_reply, summarize
from app.agent.sse import iter_graph_events
from app.agent.tools import ToolContext
from app.packs.registry import get_configurator
from app.packs.software_outsourcing.configurator import (
    SoftwareOutsourcingConfigurator,
    sample_complexity,
)
from app.packs.software_outsourcing.requirement import SoftwareRequirement
from tests.unit.test_agent import names, software_deps


def item(doc: str, fields: list[str], quality: str = "clear") -> SampleItem:
    return SampleItem(name="a.jpg", doc_type=doc, fields=fields, quality=quality)  # type: ignore[arg-type]


def cfg() -> SoftwareOutsourcingConfigurator:
    c = get_configurator("software_outsourcing")
    assert isinstance(c, SoftwareOutsourcingConfigurator)
    return c


SAMPLES = SamplesIn(
    total=6,
    items=[
        item("增值税发票", ["发票号码", "开票日期", "金额"]),
        item("增值税发票", ["发票号码", "金额", "税额"], "blurry"),
        item("装箱单", ["箱号", "件数"]),
        item("装箱单", ["箱号", "毛重"], "handwritten"),
        item("提单", ["提单号", "船名"]),
    ],
)


def test_parse_reply_tolerates_extra_text_and_bad_values() -> None:
    got = parse_reply(
        "a.jpg",
        '好的：\n```json\n{"doc_type": "发票", "fields": ["金额", "金额", ""],'
        ' "quality": "x"}\n```',
    )
    assert (got.doc_type, got.fields, got.quality) == ("发票", ["金额"], "clear")
    assert parse_reply("a.jpg", '{"fields": "金额"}').doc_type == "其他"
    with pytest.raises(ValueError):
        parse_reply("a.jpg", "看不清")


def test_summarize_groups_by_type_and_orders_fields() -> None:
    s = summarize(SAMPLES)
    assert (s.total, s.analyzed, s.blurry, s.handwritten) == (6, 5, 1, 1)
    assert [(t.name, t.count) for t in s.types] == [("增值税发票", 2), ("装箱单", 2), ("提单", 1)]
    assert s.types[0].fields[:2] == ["发票号码", "金额"]  # 出现次数多的在前
    text = sample_lib.describe(s)
    assert "6 张样例图片，识别了 5 张，共 3 类单据" in text and "模糊 1 张、手写 1 张" in text
    # 用户气泡只显示用户的话
    assert strip(sample_lib.compose("按样例出方案", s)) == "按样例出方案"


def test_samples_field_is_not_extracted_by_llm() -> None:
    assert "samples" not in optional_model(SoftwareRequirement).model_fields
    assert "modules" in optional_model(SoftwareRequirement).model_fields


def test_sample_complexity() -> None:
    s = summarize(SAMPLES)
    assert sample_complexity(s) == "complex"  # 3 类单据
    one = summarize(SamplesIn(total=2, items=[item("发票", ["金额"]), item("发票", ["金额"])]))
    assert sample_complexity(one) == "simple"
    hand = summarize(SamplesIn(total=2, items=[item("收据", []), item("收据", [], "handwritten")]))
    assert sample_complexity(hand) == "complex"  # 手写占一半


def test_apply_samples_adds_ocr_module_and_platform() -> None:
    s = summarize(SAMPLES).model_dump()
    out = cfg().apply_samples({"modules": [{"key": "file", "name": "上传"}]}, s)
    ocr = next(m for m in out["modules"] if m["key"] == "ocr")
    assert ocr["complexity"] == "complex" and ocr["source"] == "inferred"
    assert "增值税发票" in ocr["name"] and out["platforms"] == ["web"]
    # 已有识别模块：只按样例改复杂度
    mods = [{"key": "ocr", "name": "票据识别", "complexity": "simple", "source": "mentioned"}]
    kept = cfg().apply_samples({"modules": mods, "platforms": ["app"]}, s)
    assert [(m["name"], m["complexity"]) for m in kept["modules"]] == [("票据识别", "complex")]
    assert kept["platforms"] == ["app"] and kept["samples"]["analyzed"] == 5


def test_clarify_with_samples_notes_and_question() -> None:
    s = summarize(SAMPLES).model_dump()
    r = SoftwareRequirement.model_validate(
        cfg().apply_samples({"modules": [{"key": "file", "name": "上传"}], "questions": ["Q"]}, s)
    )
    info = cfg().clarify(r)
    assert info["notes"][0].startswith("样例分析：6 张里识别出 3 类单据")
    assert "1 张没识别出来" in info["notes"][0]
    assert any("这 6 张样例做识别验证" in n for n in info["notes"])
    assert info["questions"][0].startswith("样例里增值税发票识别出的字段有 发票号码、金额")
    assert info["questions"][1] == "Q"


def test_chat_with_samples_goes_to_requirement_card(tool_ctx: ToolContext) -> None:
    """带样例聊天：不论这句话怎么说都走出方案，需求卡片里有识别模块和样例汇总。"""
    saver, deps = InMemorySaver(), software_deps(tool_ctx)
    run = service.prepare_chat(
        deps, "客户发来的单据，做个系统录入", None, checkpointer=saver, samples=SAMPLES
    )
    events = list(iter_graph_events(run.graph, run.payload, run.config, run.thread_id))
    assert names(events)[-1] == "done"
    card = next(e for e in events if e["event"] == "artifact")["data"]
    assert card["type"] == "requirement"
    req = card["data"]["requirement"]
    assert any(m["key"] == "ocr" and m["complexity"] == "complex" for m in req["modules"])
    assert req["samples"]["types"][0]["name"] == "增值税发票"
    text = "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
    assert "样例分析" in text
    # 确认需求：样例汇总随需求保留，销售改过的复杂度不会被改回去
    for m in req["modules"]:
        if m["key"] == "ocr":
            m["complexity"] = "medium"
    confirm = service.prepare_chat(
        deps, "需求已确认，出正式报价", None, checkpointer=saver, requirement=req
    )
    second = list(
        iter_graph_events(confirm.graph, confirm.payload, confirm.config, confirm.thread_id)
    )
    tiers = next(e for e in second if e["event"] == "artifact")["data"]["data"]
    ocr_line = next(i for i in tiers[1]["items"] if i["sku"] == "MOD-OCR")
    assert "（中等）" in ocr_line["name"]
