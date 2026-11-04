"""学习问答（新人带教）用的只读工具：公司业务概览，全部来自系统配置，不编造。

产品线和目录、销售阶段和赢率、报价 / 提成 / 报销规则、竞品名单——这些都在系统里配置着，
新销售问「公司卖什么、报价怎么算、单子怎么推进」时按它回答；不给成本和毛利。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.models import Competitor, ProductLine
from app.crm.schemas.opportunity import STAGE_LABELS, STAGES
from app.crm.services import catalog_service
from app.crm.services.rule_notes import CATEGORY_LABELS, rule_notes
from app.packs.registry import list_packs
from app.rules.loader import load_rules


class OverviewArgs(BaseModel):
    topic: str | None = Field(
        default=None,
        description="products 产品线与目录 / pipeline 销售阶段 / rules 报价提成报销规则 / "
        "competitors 竞品名单；不填返回全部",
    )


def _products(db: Any) -> list[dict[str, Any]]:
    packs = list_packs()
    lines = db.scalars(select(ProductLine).where(ProductLine.enabled).order_by(ProductLine.name))
    out = []
    for line in lines:
        pack = packs.get(line.pack)
        if pack is None:
            continue
        catalog: dict[str, list[str]] = {}
        for row in catalog_service.catalog_rows(pack):
            label = CATEGORY_LABELS.get(row.category, row.category)
            item = f"{row.name}（{row.unit}，目录价 ¥{row.price / 100:,.0f}）"
            catalog.setdefault(label, []).append(item)
        out.append(
            {
                "product_line": line.name,
                "pack": pack.name,
                "description": pack.description,
                "sample_data": pack.sample_data,
                "catalog": catalog,
            }
        )
    return out


def _pipeline() -> list[dict[str, Any]]:
    rates = load_rules().pipeline.stage_win_rate
    return [{"stage": STAGE_LABELS[s], "default_win_rate": f"{rates.get(s, 0)}%"} for s in STAGES]


def _rules() -> dict[str, Any]:
    notes = rule_notes(load_rules())
    return {
        k: {"title": n.title, "items": {i.label: i.value for i in n.items}, "note": n.note}
        for k, n in notes.items()
    }


def get_business_overview(ctx: ToolContext, args: OverviewArgs) -> ToolResult:
    topic = (args.topic or "").strip()
    data: dict[str, Any] = {}
    with ctx.session() as db:
        if topic in ("", "products"):
            data["products"] = _products(db)
        if topic in ("", "competitors"):
            rows = db.scalars(select(Competitor.name).where(Competitor.enabled))
            data["competitors"] = sorted(rows)
    if topic in ("", "pipeline"):
        data["pipeline"] = _pipeline()
    if topic in ("", "rules"):
        data["rules"] = _rules()
    data["source"] = "系统配置（产品目录、业务规则、竞品战卡）"
    sample = any(p.get("sample_data") for p in data.get("products", []))
    summary = "业务概览" + ("（产品目录为示例资料）" if sample else "")
    return ToolResult(ok=True, summary=summary, data=data)


LEARN_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "get_business_overview",
        "查公司业务概览：有哪些产品线、各自卖什么（目录价）、销售阶段和默认赢率、"
        "报价折扣审批 / 提成 / 报销规则、主要竞品名单。新人问公司业务、产品、流程、规则时使用",
        OverviewArgs,
        get_business_overview,
    ),
]
