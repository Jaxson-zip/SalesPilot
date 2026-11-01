"""按客户预算收缩经济版：先把功能都做成基础版，还放不下就把排在后面的模块挪到二期。

只减范围、不压单价：价格仍由配置器按人天单价算，毛利规则照常校验。
收缩后连一个模块都放不进预算时不收缩，经济版保持原样（配置器会提示预算缺口）。
"""

from collections.abc import Callable

from app.packs.base import SolutionTier
from app.packs.software_outsourcing.requirement import (
    Module,
    SoftwareRequirement,
    dedupe_modules,
)

Build = Callable[[SoftwareRequirement], SolutionTier]


def _drop_order(mods: list[Module]) -> list[Module]:
    """先挪 AI 推断的（客户没提），再挪客户提到的；各自从排在后面的开始。"""
    inferred = [m for m in mods if m.source == "inferred"]
    mentioned = [m for m in mods if m.source != "inferred"]
    return [*reversed(inferred), *reversed(mentioned)]


def fit_budget(r: SoftwareRequirement, budget: int, build: Build) -> SolutionTier | None:
    """返回放得进预算的经济版（summary 里写明怎么收缩的）；怎么收缩都放不下返回 None。"""
    mods = dedupe_modules(r.modules)
    mods = [m for m in mods if m.must] or mods
    keep = [m.model_copy(update={"complexity": "simple"}) for m in mods]
    deferred: list[str] = []
    queue = _drop_order(keep)
    while keep:
        tier = build(r.model_copy(update={"modules": keep}))
        if tier.total_price <= budget:
            return _with_note(tier, budget, deferred)
        if len(keep) == 1:
            return None
        drop = queue.pop(0)
        keep = [m for m in keep if m is not drop]
        deferred.insert(0, drop.name)
    return None


def _with_note(tier: SolutionTier, budget: int, deferred: list[str]) -> SolutionTier:
    note = f"（按客户预算 {budget / 1_000_000:.1f} 万收缩：功能按基础版做"
    if deferred:
        note += "；二期再做：" + "、".join(deferred)
    return tier.model_copy(update={"summary": tier.summary + note + "）"})
