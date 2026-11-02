"""报价单对外的项目范围：按这一档、调整后的明细算实际交付的端和功能，并列出不包含的。

经济版只做首期模块、第一个客户端；销售在报价单里删掉的模块也不算。分享页和打印版
如果直接用整份需求清单，会把二期功能、没报价的 App 写进项目范围，签约后容易扯皮。
"""

from typing import Any, Protocol

from app.packs.software_outsourcing.requirement import (
    Module,
    SoftwareRequirement,
    dedupe_modules,
)

Items = list[tuple[str, str]]  # 报价明细的 (sku, 名称)
Scope = dict[str, Any]


class TierPlan(Protocol):
    """configurator._Plan 里用到的部分：这一档做哪些端、哪些模块、几个人做。"""

    team: int
    platforms: list[str]
    mods: list[Module]


def _quoted(m: Module, names: list[str]) -> bool:
    """明细名称是「模块名（复杂度）」：按模块名前缀判断这个模块还在不在报价里。"""
    return any(n.startswith(f"{m.name}（") for n in names)


def tier_scope(r: SoftwareRequirement, plan: TierPlan, items: Items) -> Scope:
    """返回交付端、功能模块、交付人数，以及需求里有但这次不含的。"""
    skus = {sku for sku, _ in items}
    names = [name for sku, name in items if sku.startswith("MOD-")]
    modules = [m for m in plan.mods if _quoted(m, names)]
    platforms = [p for p in plan.platforms if p != "admin" or "SVC-ADMIN" in skus]
    kept = {m.name for m in modules}
    return {
        "platforms": platforms,
        "modules": [{"name": m.name, "must": m.must} for m in modules],
        "team_size": plan.team,
        "excluded_platforms": [p for p in r.platforms if p not in platforms],
        "excluded_modules": [m.name for m in dedupe_modules(r.modules) if m.name not in kept],
    }
