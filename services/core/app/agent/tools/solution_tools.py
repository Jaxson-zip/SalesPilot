"""出方案类工具：需求解析、行业包配置、目录查询、毛利校验、生成报价单。

行业包由调用方（图节点）从商机产品线解析后传入 pack_id，不接受用户在对话里指定。
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.services import quote_service
from app.packs.base import Catalog, SolutionTier
from app.packs.registry import get_configurator, get_pack
from app.rules import check_margin as rule_check_margin
from app.rules import load_rules


class ParseRequirementArgs(BaseModel):
    pack_id: str
    text: str = Field(max_length=4000)
    draft: dict[str, Any] = Field(default_factory=dict, description="之前轮次已识别的字段")
    extracted: dict[str, Any] = Field(default_factory=dict, description="大模型结构化输出")


def missing_fields(model: type[BaseModel], data: dict[str, Any]) -> list[str]:
    try:
        model.model_validate(data)
    except ValidationError as exc:
        return sorted({str(e["loc"][0]) if e["loc"] else "__root__" for e in exc.errors()})
    return []


def parse_requirement(ctx: ToolContext, args: ParseRequirementArgs) -> ToolResult:
    configurator = get_configurator(args.pack_id)
    merged = {**args.draft, **configurator.draft_requirement(args.text), **args.extracted}
    if fill := getattr(configurator, "fill_defaults", None):  # 可选：行业包在合并后补默认值
        merged = fill(merged)
    missing = missing_fields(configurator.requirement_model, merged)
    summary = "需求完整" if not missing else f"缺少：{', '.join(missing)}"
    return ToolResult(ok=True, summary=summary, data={"requirement": merged, "missing": missing})


class ConfigureArgs(BaseModel):
    pack_id: str
    requirement: dict[str, Any]
    hint: str | None = None


def configure_solution(ctx: ToolContext, args: ConfigureArgs) -> ToolResult:
    configurator = get_configurator(args.pack_id)
    req = configurator.requirement_model.model_validate(args.requirement)
    tiers = configurator.configure(req, args.hint)
    data = [t.model_dump(mode="json") for t in tiers]
    vram = tiers[0].specs.get("vram") if tiers else None
    summary = f"生成 {len(tiers)} 档方案"
    if isinstance(vram, dict):
        summary += f"，{vram['precision'].upper()} 约需 {vram['total_gb']} GB 显存起"
    return ToolResult(ok=True, summary=summary, data=data)


class QueryCatalogArgs(BaseModel):
    pack_id: str
    keyword: str = ""
    category: str | None = None


def query_catalog(ctx: ToolContext, args: QueryCatalogArgs) -> ToolResult:
    catalog = Catalog.from_file(get_pack(args.pack_id).path / "catalog.json")
    items = catalog.search(args.keyword, args.category)
    return ToolResult(
        ok=True, summary=f"筛选出 {len(items)} 个产品", data=[i.model_dump() for i in items]
    )


class TierPrice(BaseModel):
    tier: str
    total_cost: int = Field(ge=0)
    total_price: int = Field(ge=0)


class CheckMarginArgs(BaseModel):
    pack_id: str
    tiers: list[TierPrice]


def check_margin(ctx: ToolContext, args: CheckMarginArgs) -> ToolResult:
    rules = load_rules(get_pack(args.pack_id).rules_file, scope=args.pack_id)
    results = [
        {"tier": t.tier, **rule_check_margin(t.total_cost, t.total_price, rules).model_dump()}
        for t in args.tiers
    ]
    failed = [r for r in results if not r["passed"]]
    if failed:
        summary = "；".join(f"{r['tier']} {r['reason']}" for r in failed)
    else:
        summary = "全部档位毛利达标"
    return ToolResult(ok=True, summary=summary, data={"passed": not failed, "results": results})


class GenerateQuoteArgs(BaseModel):
    pack_id: str
    tier: SolutionTier
    opportunity_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=100)


def generate_quote(ctx: ToolContext, args: GenerateQuoteArgs) -> ToolResult:
    with ctx.session() as db:
        quote = quote_service.create_from_tier(
            db,
            ctx.user,
            pack=args.pack_id,
            tier=args.tier,
            opportunity_id=args.opportunity_id,
            idempotency_key=args.idempotency_key,
            customer_id=args.customer_id,
        )
    return ToolResult(
        ok=True, summary=f"报价单 {quote.code} 已创建", data=quote.model_dump(mode="json")
    )


SOLUTION_TOOLS: list[ToolSpec] = [
    ToolSpec("parse_requirement", "输出结构化需求", ParseRequirementArgs, parse_requirement),
    ToolSpec("configure_solution", "分发给当前行业包的配置器", ConfigureArgs, configure_solution),
    ToolSpec("query_catalog", "查询产品目录", QueryCatalogArgs, query_catalog),
    ToolSpec("check_margin", "规则代码计算毛利", CheckMarginArgs, check_margin),
    ToolSpec(
        "generate_quote",
        "生成报价单（幂等）",
        GenerateQuoteArgs,
        generate_quote,
        write=True,
        needs_confirm=True,
    ),
]
