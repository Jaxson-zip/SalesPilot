"""软件外包配置器：功能模块拆解 → 估人天 → 经济 / 标准 / 高配三档 → 按角色人天单价定价。

- 拆解（哪些模块、多复杂）由大模型完成，是方案的初稿，销售和客户确认后可以在报价单里改人天；
- 每个模块的人天、各项比例、团队人数都来自 rules.yaml 的 pack 段（管理员可在网页改），
  不让大模型估数字；
- 单价来自产品目录（研发 / UI / 测试 / 产品经理人天，部署、运维、源码交付）。
"""

import math
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.packs.base import TIER_NAMES, BomItem, Catalog, SolutionTier, price_tier
from app.packs.software_outsourcing.requirement import (
    COMPLEXITY_NAMES,
    PLATFORM_NAMES,
    Module,
    SoftwareRequirement,
)
from app.rules import RuleSet, load_rules
from app.rules.loader import load_raw_rules

PACK_DIR = Path(__file__).parent
CLIENT_PLATFORMS = ("web", "mini_program", "app")
_PLATFORM_WORDS: dict[str, tuple[str, ...]] = {
    "mini_program": ("小程序",),
    "app": ("app", "安卓", "android", "ios", "苹果"),
    "web": ("网站", "官网", "h5", "网页", "web"),
    "admin": ("后台", "管理端", "管理系统"),
}
_WEEKS_RE = re.compile(r"(\d+)\s*(个月|月|周|星期)")
_BUDGET_RE = re.compile(r"预算\s*(?:在|约|为)?\s*(\d+(?:\.\d+)?)\s*(万|元)?")


class SoftwareOutsourcingConfigurator:
    requirement_model: type[BaseModel] = SoftwareRequirement

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

    # ---------- 需求 ----------

    def extract_hint(self) -> str:
        """给大模型的拆解说明：模块库、复杂度和首期判断（数字一律不让模型估）。"""
        lib = "；".join(f"{k}={m['name']}" for k, m in self.params["modules"].items())
        return (
            "这是软件外包项目。modules 需要你把客户描述的业务拆解成功能模块"
            "（这一项可以根据业务常识推断，"
            "例如「预约小程序」通常包含 用户登录、预约排期、消息通知）："
            f"优先使用模块库里的 key：{lib}。模块库没有的功能用 key=custom 并写清名称。"
            "同一个功能只出现一次；复杂度按描述判断（多规则、多角色、需对接外部系统 → complex）；"
            "客户说「以后再做 / 二期」的模块 must=false。"
            "platforms 只填客户明确提到或业务上必然需要的端（提到管理、运营、后台配置时加 admin）。"
            "不要估算人天和价格。"
        )

    def draft_requirement(self, text: str) -> dict[str, Any]:
        """规则兜底：按关键词识别端和标准模块（大模型不可用时也能出一版）。"""
        low = text.lower()
        draft: dict[str, Any] = {}
        platforms = [p for p, words in _PLATFORM_WORDS.items() if any(w in low for w in words)]
        if platforms:
            draft["platforms"] = platforms
        modules = [
            {"key": key, "name": m["name"], "complexity": "medium", "must": True}
            for key, m in self.params["modules"].items()
            if any(w.lower() in low for w in m.get("keywords", []))
        ]
        if modules:
            draft["modules"] = modules
        if m := _WEEKS_RE.search(text):
            n = int(m.group(1))
            draft["deadline_weeks"] = n * 4 if "月" in m.group(2) else n
        if m := _BUDGET_RE.search(text):
            value = float(m.group(1)) * (10000 if m.group(2) == "万" else 1)
            draft["budget"] = round(value * 100)
        return draft

    # ---------- 配置 ----------

    def configure(self, req: BaseModel, hint: str | None = None) -> list[SolutionTier]:
        r = SoftwareRequirement.model_validate(req.model_dump())
        tiers = [
            price_tier(self._build_tier(t, r), self.rules)
            for t in ("economy", "standard", "premium")
        ]
        pick = self._recommend(tiers, r.budget)
        return [t.model_copy(update={"recommended": t.tier == pick}) for t in tiers]

    @staticmethod
    def _recommend(tiers: list[SolutionTier], budget: int | None) -> str:
        """默认推荐标准版；客户预算放不下标准版、但放得下经济版时推荐经济版。"""
        by = {t.tier: t for t in tiers}
        if budget and by["standard"].total_price > budget >= by["economy"].total_price:
            return "economy"
        return "standard"

    def module_days(self, m: Module) -> int:
        lib = self.params["modules"]
        days = lib.get(m.key, self.params["custom_module"])["days"]
        return int(days[["simple", "medium", "complex"].index(m.complexity)])

    def _build_tier(self, tier_id: str, r: SoftwareRequirement) -> SolutionTier:
        p = self.params
        cfg = p["tiers"][tier_id]
        clients = [x for x in r.platforms if x in CLIENT_PLATFORMS]
        if cfg["platforms"] == "first":
            clients = clients[:1]
        platforms = clients + (["admin"] if "admin" in r.platforms else [])
        # 多端：每多一个客户端，模块工作量 × (1 + 系数)
        factor = 1 + p["extra_platform_factor"] * max(len(clients) - 1, 0)

        mods = _dedupe(r.modules)
        if cfg["scope"] == "must":
            mods = [m for m in mods if m.must] or mods

        dev = self.catalog.get("DAY-DEV")
        items: list[BomItem] = [
            self._days("SVC-ARCH", "技术架构与数据库设计", "DAY-DEV", p["base_days"])
        ]
        if "admin" in platforms:
            items.append(self._days("SVC-ADMIN", "管理后台基础框架", "DAY-DEV", p["admin_days"]))
        for i, m in enumerate(mods):
            sku = f"MOD-{m.key.upper()}" if m.key != "custom" else f"MOD-CUSTOM-{i + 1}"
            items.append(
                BomItem(
                    sku=sku,
                    name=f"{m.name}（{COMPLEXITY_NAMES[m.complexity]}）",
                    category="service",
                    unit="人天",
                    qty=math.ceil(self.module_days(m) * factor),
                    unit_cost=dev.cost,
                    unit_price=dev.price,
                )
            )
        dev_days = sum(i.qty for i in items)
        ratios = {**p["ratios"], **cfg.get("ratios", {})}
        items.insert(
            0,
            self._days(
                "SVC-ANALYSIS", "需求分析与原型设计", "DAY-PM", dev_days * ratios["analysis"]
            ),
        )
        if clients:
            items.append(self._days("SVC-UI", "UI 设计", "DAY-UI", dev_days * ratios["ui"]))
        items.append(self._days("SVC-QA", "测试与验收", "DAY-QA", dev_days * ratios["qa"]))
        items.append(self._days("SVC-PM", "项目管理", "DAY-PM", dev_days * ratios["pm"]))
        items.append(
            self._days("SVC-BUFFER", "需求变更与风险预留", "DAY-DEV", dev_days * ratios["buffer"])
        )
        items.append(self.catalog.line("SVC-DEPLOY", 1))
        if cfg["ops_months"]:
            items.append(self.catalog.line("SVC-OPS", cfg["ops_months"]))
        if cfg["handover"]:
            items.append(self.catalog.line("SVC-HANDOVER", 1))

        person_days = sum(i.qty for i in items if i.unit == "人天")
        weeks = math.ceil(person_days / p["team_size"] / 5)
        names = "、".join(PLATFORM_NAMES[x] for x in platforms)
        summary = (
            f"{len(mods)} 个功能模块 · {names} · 约 {person_days} 人天，"
            f"{p['team_size']} 人约 {weeks} 周"
        )
        if r.deadline_weeks and weeks > r.deadline_weeks:
            summary += f"（比期望工期多 {weeks - r.deadline_weeks} 周，需加人或分期）"
        return SolutionTier(
            tier=tier_id,  # type: ignore[arg-type]
            name=TIER_NAMES[tier_id],
            summary=summary,
            items=items,
            specs={
                "platforms": platforms,
                "modules": [
                    {
                        "name": m.name,
                        "complexity": m.complexity,
                        "must": m.must,
                        "days": self.module_days(m),
                    }
                    for m in mods
                ],
                "person_days": person_days,
                "weeks": weeks,
            },
        )

    def _days(self, sku: str, name: str, rate_sku: str, days: float) -> BomItem:
        """按某个角色的人天单价生成一行（人天向上取整，至少 1 天）。"""
        rate = self.catalog.get(rate_sku)
        return BomItem(
            sku=sku,
            name=name,
            category="service",
            unit="人天",
            qty=max(1, math.ceil(days)),
            unit_cost=rate.cost,
            unit_price=rate.price,
        )


def _dedupe(modules: list[Module]) -> list[Module]:
    """同一个标准模块只算一次（自定义模块按名称去重）。"""
    seen: set[str] = set()
    out: list[Module] = []
    for m in modules:
        k = m.key if m.key != "custom" else f"custom:{m.name}"
        if k not in seen:
            seen.add(k)
            out.append(m)
    return out


def create_configurator() -> SoftwareOutsourcingConfigurator:
    return SoftwareOutsourcingConfigurator()
