"""企业办公 IT 配置器：按岗位人数配电脑、显示器，按座位数配交换机和无线 AP，
设计岗位配共享存储，生成三档 BOM。数量比例在 rules.yaml 的 pack 段。"""

import math
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.packs.base import (
    TIER_NAMES,
    BomItem,
    Catalog,
    SolutionTier,
    price_tier,
    recommend_for_budget,
)
from app.packs.it_office.requirement import ItOfficeRequirement
from app.rules import RuleSet, load_rules
from app.rules.loader import load_raw_rules

PACK_DIR = Path(__file__).parent
_OFFICE_RE = re.compile(r"(\d+)\s*(?:个|名|位)?\s*(?:行政|办公|普通)")
_DESIGN_RE = re.compile(r"(\d+)\s*(?:个|名|位)?\s*设计")
_HAS_NETWORK_RE = re.compile(r"已有网络|网络已有|不(?:需要|用)(?:配)?网络")


class ItOfficeConfigurator:
    requirement_model: type[BaseModel] = ItOfficeRequirement

    # 每次读取：管理员在网页上改了价格 / 规则 / 参数后立即生效（configurator 本身被缓存）
    @property
    def catalog(self) -> Catalog:
        return Catalog.from_file(PACK_DIR / "catalog.json", scope=PACK_DIR.name)

    @property
    def rules(self) -> RuleSet:
        return load_rules(PACK_DIR / "rules.yaml", scope=PACK_DIR.name)

    @property
    def params(self) -> dict[str, Any]:
        pack: dict[str, Any] = load_raw_rules(PACK_DIR / "rules.yaml", scope=PACK_DIR.name)["pack"]
        return pack

    def draft_requirement(self, text: str) -> dict[str, Any]:
        draft: dict[str, Any] = {}
        if m := _OFFICE_RE.search(text):
            draft["office_staff"] = int(m.group(1))
        if m := _DESIGN_RE.search(text):
            draft["designers"] = int(m.group(1))
        if _HAS_NETWORK_RE.search(text):
            draft["network"] = False
        return draft

    def configure(self, req: BaseModel, hint: str | None = None) -> list[SolutionTier]:
        r = ItOfficeRequirement.model_validate(req.model_dump())
        tiers = [self._build_tier(t, r) for t in ("economy", "standard", "premium")]
        priced = [price_tier(t, self.rules) for t in tiers]
        return recommend_for_budget(priced, r.budget, "建议分批采购或调整配置")

    def _build_tier(self, tier_id: str, r: ItOfficeRequirement) -> SolutionTier:
        cfg = self.params["tiers"][tier_id]
        items: list[BomItem] = []
        if r.office_staff:
            items.append(self.catalog.line(cfg["office"], r.office_staff))
        if r.designers:
            items.append(self.catalog.line(cfg["design"], r.designers))
            if cfg["monitor_for_design"]:
                items.append(self.catalog.line("MON-27-4K", r.designers))
        seats = r.office_staff + r.designers
        items += self._infra(cfg, r, seats)
        items.append(self.catalog.line("SVC-INSTALL", seats))
        if cfg["warranty"]:
            items.append(self.catalog.line("SVC-WARRANTY-3Y", seats))
        return SolutionTier(
            tier=tier_id,  # type: ignore[arg-type]
            name=TIER_NAMES[tier_id],
            summary=f"{r.office_staff} 台办公机 + {r.designers} 台设计工作站",
            items=items,
            recommended=tier_id == "standard",
            specs={"seats": seats},
        )

    def _infra(self, cfg: dict[str, Any], r: ItOfficeRequirement, seats: int) -> list[BomItem]:
        """网络（按座位数）和共享存储（按设计岗位数），台数向上取整。"""
        p = self.params
        items: list[BomItem] = []
        if r.network:
            items.append(self.catalog.line("NET-SW-24", math.ceil(seats / p["seats_per_switch"])))
            items.append(self.catalog.line("NET-AP", math.ceil(seats / p["seats_per_ap"])))
        if cfg["nas"] and r.designers:
            nas = math.ceil(r.designers / p["designers_per_nas"])
            items.append(self.catalog.line("NAS-4BAY", nas))
        return items


def create_configurator() -> ItOfficeConfigurator:
    return ItOfficeConfigurator()
