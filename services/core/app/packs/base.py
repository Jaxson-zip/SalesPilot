"""行业包接口（开发规范 §7）：Configurator Protocol、方案档位、物料行与通用定价函数。

packs 不依赖 crm / agent 的内部实现；金额单位一律为整数「分」。
"""

import json
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.rules import RuleSet, check_margin, overrides

Category = Literal["hardware", "software", "service"]
TierId = Literal["economy", "standard", "premium"]
TIER_NAMES: dict[str, str] = {"economy": "经济版", "standard": "标准版", "premium": "高配版"}


class CatalogItem(BaseModel):
    sku: str
    name: str
    category: Category
    unit: str
    cost: int  # 成本（分）
    price: int  # 目录价（分）
    specs: dict[str, Any] = Field(default_factory=dict)


class BomItem(BaseModel):
    sku: str
    name: str
    category: Category
    unit: str
    qty: int
    unit_cost: int
    unit_price: int

    @property
    def total_cost(self) -> int:
        return self.unit_cost * self.qty

    @property
    def total_price(self) -> int:
        return self.unit_price * self.qty


class SolutionTier(BaseModel):
    tier: TierId
    name: str
    summary: str
    items: list[BomItem]
    discount_rate: float = 0.0
    total_cost: int = 0
    total_price: int = 0
    margin_rate: float = 0.0
    margin_ok: bool = False
    recommended: bool = False
    specs: dict[str, Any] = Field(default_factory=dict)


class SampleType(BaseModel):
    """客户样例里的一类单据 / 表单。"""

    name: str
    count: int
    fields: list[str] = Field(default_factory=list)


class SampleSummary(BaseModel):
    """客户样例图片的识别汇总（不含原图和字段值，只有类型、字段名和清晰度）。"""

    total: int = Field(description="上传的张数")
    analyzed: int = Field(description="识别成功的张数")
    types: list[SampleType] = Field(default_factory=list)
    blurry: int = 0
    handwritten: int = 0


@runtime_checkable
class Configurator(Protocol):
    """行业包配置器：需求 → 多档 BOM。"""

    requirement_model: type[BaseModel]

    def configure(self, req: BaseModel, hint: str | None = None) -> list[SolutionTier]: ...

    def draft_requirement(self, text: str) -> dict[str, Any]:
        """规则兜底的需求抽取（大模型结构化输出不可用时使用），返回已识别的字段。"""
        ...


class Catalog:
    """产品目录（catalog.json）。"""

    def __init__(self, items: list[CatalogItem]) -> None:
        self._items = {item.sku: item for item in items}

    @classmethod
    def from_file(cls, path: Path, scope: str | None = None) -> "Catalog":
        """读取 catalog.json；传入行业包 id 时合并管理员在网页上改过的名称、单位、成本、售价。"""
        raw = json.loads(path.read_text(encoding="utf-8"))
        edits = overrides.nested(scope, "catalog").get("catalog", {}) if scope else {}
        items = [{**i, **edits.get(i["sku"], {})} for i in raw["items"]]
        return cls([CatalogItem.model_validate(i) for i in items])

    def get(self, sku: str) -> CatalogItem:
        return self._items[sku]

    def all(self) -> list[CatalogItem]:
        return list(self._items.values())

    def search(self, keyword: str = "", category: str | None = None) -> list[CatalogItem]:
        kw = keyword.lower()
        return [
            i
            for i in self._items.values()
            if (not kw or kw in i.name.lower() or kw in i.sku.lower())
            and (category is None or i.category == category)
        ]

    def line(self, sku: str, qty: int) -> BomItem:
        item = self.get(sku)
        return BomItem(
            sku=item.sku,
            name=item.name,
            category=item.category,
            unit=item.unit,
            qty=qty,
            unit_cost=item.cost,
            unit_price=item.price,
        )


class MarginHint(BaseModel):
    """毛利回退时传给配置器的调整提示（序列化为 hint 字符串）。"""

    attempt: int = 0
    low_tiers: list[str] = Field(default_factory=list)

    def dump(self) -> str:
        return self.model_dump_json()

    @classmethod
    def parse(cls, hint: str | None) -> "MarginHint":
        if not hint:
            return cls()
        try:
            return cls.model_validate_json(hint)
        except ValueError:
            return cls()


def price_tier(tier: SolutionTier, rules: RuleSet) -> SolutionTier:
    """按物料汇总成本与售价，应用整单折扣，并用规则引擎计算毛利。"""
    total_cost = sum(i.total_cost for i in tier.items)
    list_price = sum(i.total_price for i in tier.items)
    total_price = round(list_price * (1 - tier.discount_rate))
    margin = check_margin(total_cost, total_price, rules)
    return tier.model_copy(
        update={
            "total_cost": total_cost,
            "total_price": total_price,
            "margin_rate": margin.margin_rate,
            "margin_ok": margin.passed,
        }
    )
