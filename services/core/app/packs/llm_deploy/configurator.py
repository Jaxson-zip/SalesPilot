"""大模型部署配置器：显存估算 → GPU 选型 → 经济 / 标准 / 高配三档 BOM → 规则定价。"""

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.packs.base import (
    TIER_NAMES,
    BomItem,
    Catalog,
    CatalogItem,
    MarginHint,
    SolutionTier,
    price_tier,
)
from app.packs.llm_deploy.requirement import LlmDeployRequirement
from app.packs.llm_deploy.vram import GpuPlan, estimate_vram, find_model, model_specs, plan_gpus
from app.rules import RuleSet, load_rules
from app.rules.loader import load_raw_rules

PACK_DIR = Path(__file__).parent
_CONCURRENCY_RE = re.compile(r"(\d+)\s*(?:人|个用户|路|个)?\s*并发|并发\s*(\d+)")
_BUDGET_RE = re.compile(r"预算\s*(?:在|约|为)?\s*(\d+(?:\.\d+)?)\s*(万|元)?")


class LlmDeployConfigurator:
    requirement_model: type[BaseModel] = LlmDeployRequirement

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
        spec = find_model(text)
        if spec:
            draft["model_name"] = spec.name
        if m := _CONCURRENCY_RE.search(text):
            draft["concurrency"] = int(m.group(1) or m.group(2))
        if m := _BUDGET_RE.search(text):
            value = float(m.group(1)) * (10000 if m.group(2) == "万" else 1)
            draft["budget"] = round(value * 100)
        for scene in ("合同审查", "客服", "知识库", "质检", "病历"):
            if scene in text:
                draft["scene"] = scene
        return draft

    def configure(self, req: BaseModel, hint: str | None = None) -> list[SolutionTier]:
        r = LlmDeployRequirement.model_validate(req.model_dump())
        spec = model_specs().get(r.model_name)
        if spec is None:
            raise ValueError(f"暂不支持的模型：{r.model_name}")
        margin_hint = MarginHint.parse(hint)
        tiers = [
            self._build_tier(tier_id, r, margin_hint)
            for tier_id in ("economy", "standard", "premium")
        ]
        return [price_tier(t, self.rules) for t in tiers]

    def _build_tier(self, tier_id: str, r: LlmDeployRequirement, hint: MarginHint) -> SolutionTier:
        cfg = self.params["tiers"][tier_id]
        spec = model_specs()[r.model_name]
        ctx = r.context_tokens or int(self.params["default_context_tokens"])
        est = estimate_vram(
            spec, cfg["precision"], r.concurrency, ctx, float(self.params["vram_headroom"])
        )
        server = self._servers(cfg["gpu"])[-1]
        plan = plan_gpus(
            est.total_gb, int(server.specs["gpu_mem_gb"]), self.params["tensor_parallel_sizes"]
        )
        server, nodes = self._pick_server(cfg["gpu"], plan)
        if cfg["ha"]:
            nodes *= 2
        items = self._bom(server, nodes, cfg)
        gpus = int(server.specs["gpus"]) * nodes
        summary = (
            f"{gpus}× {server.specs['gpu']} {server.specs['gpu_mem_gb']}G · "
            f"{cfg['precision'].upper()} · vLLM" + (" · 双机高可用" if cfg["ha"] else "")
        )
        return SolutionTier(
            tier=tier_id,  # type: ignore[arg-type]
            name=TIER_NAMES[tier_id],
            summary=summary,
            items=items,
            discount_rate=self._discount(tier_id, hint),
            recommended=tier_id == "standard",
            specs={"vram": est.model_dump(), "gpus": gpus, "nodes": nodes},
        )

    def _servers(self, gpu: str) -> list[CatalogItem]:
        found = [i for i in self.catalog.all() if i.specs.get("gpu") == gpu]
        return sorted(found, key=lambda i: int(i.specs["gpus"]))

    def _pick_server(self, gpu: str, plan: GpuPlan) -> tuple[CatalogItem, int]:
        """选卡数 ≥ 计划单机卡数的最小机型；没有时用最大机型并增加台数。"""
        servers = self._servers(gpu)
        need = plan.cards_per_node * plan.nodes
        for server in servers:
            if int(server.specs["gpus"]) >= plan.cards_per_node and plan.nodes == 1:
                return server, 1
        biggest = servers[-1]
        return biggest, -(-need // int(biggest.specs["gpus"]))

    def _bom(self, server: CatalogItem, nodes: int, cfg: dict[str, Any]) -> list[BomItem]:
        items = [self.catalog.line(server.sku, nodes), self.catalog.line("SVC-DEPLOY", 1)]
        if cfg["precision"] != "int4":
            items.append(self.catalog.line("SW-MONITOR", 1))
        if cfg["ha"]:
            items.append(self.catalog.line("SW-HA", 1))
        if cfg["tuning_days"]:
            items.append(self.catalog.line("SVC-TUNING", int(cfg["tuning_days"])))
        items.append(self.catalog.line("SVC-MAINT-1Y", nodes * int(cfg["maint_years"])))
        return items

    def _discount(self, tier_id: str, hint: MarginHint) -> float:
        if tier_id != "economy":
            return 0.0
        ladder: list[float] = self.params["economy_discount_ladder"]
        return ladder[min(hint.attempt, len(ladder) - 1)]


def create_configurator() -> LlmDeployConfigurator:
    return LlmDeployConfigurator()
