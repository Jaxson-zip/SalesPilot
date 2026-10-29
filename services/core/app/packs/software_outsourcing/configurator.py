"""软件外包配置器：功能模块拆解 → 估人天 → 经济 / 标准 / 高配三档 → 按角色人天单价定价。

- 拆解（哪些模块、多复杂）由大模型完成，是方案的初稿，销售和客户确认后可以在报价单里改人天；
- 每个模块的人天、各项比例、团队人数都来自 rules.yaml 的 pack 段（管理员可在网页改），
  不让大模型估数字；
- 单价来自产品目录（研发 / UI / 测试 / 产品经理人天，部署、运维、源码交付）。
"""

import json
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
# 各角色用哪个人天单价：团队按角色分开；个人全栈只有一个全栈单价
TEAM_ROLES = {"dev": "DAY-DEV", "ui": "DAY-UI", "qa": "DAY-QA", "pm": "DAY-PM"}
SOLO_ROLES = dict.fromkeys(TEAM_ROLES, "DAY-FULLSTACK")
_SOLO_WORDS = ("一个人", "个人全栈", "独立开发", "我自己做", "自己一个人", "单人")
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

    def extract_hint(self, draft: dict[str, Any] | None = None) -> str:
        """给大模型的拆解说明：模块库、复杂度和首期判断（数字一律不让模型估）。

        已有需求草稿时附上，让模型在草稿基础上改（「去掉地图」「支付改简单」），输出完整模块清单。
        """
        lib = "；".join(f"{k}={m['name']}" for k, m in self.params["modules"].items())
        current = ""
        if draft and draft.get("modules"):
            keep = {k: draft[k] for k in ("project", "platforms", "modules") if k in draft}
            current = (
                "\n当前需求草稿（JSON）："
                + json.dumps(keep, ensure_ascii=False)
                + "\n用户这句话如果在增删或修改功能 / 端，"
                "请在草稿基础上输出修改后的完整 modules / platforms；"
                "只是补充预算、工期等其他信息时不要输出 modules 和 platforms。"
            )
        return current + (
            "这是软件外包项目。modules 需要你把客户描述的业务拆解成功能模块"
            "（这一项可以根据业务常识推断，"
            "例如「预约小程序」通常包含 用户登录、预约排期、消息通知）："
            f"优先使用模块库里的 key：{lib}。模块库没有的功能用 key=custom 并写清名称。"
            "同一个功能只出现一次；复杂度按描述判断（多规则、多角色、需对接外部系统 → complex）；"
            "客户说「以后再做 / 二期」的模块 must=false。"
            "客户明确提到的功能 source=mentioned，你根据常识补充的 source=inferred。"
            "questions 写 3–5 个销售需要回头和客户确认的关键问题。"
            "platforms 只填客户明确提到或业务上必然需要的端（提到管理、运营、后台配置时加 admin）；"
            "只说「手机也能用」「网页和手机都能用」、没提 App 或小程序时"
            "按网页自适应处理，只填 web；客户没说做什么端时，按用户是谁选一个最合适的客户端"
            "（面向消费者 / 学员 / 会员的优先 mini_program，企业内部办公优先 web），"
            "不要同时加多个。"
            "客户只说了要做 App / 小程序 / 系统、没说是什么业务时，modules 留空（交给销售追问），"
            "不要凭空拆解。不要估算人天和价格。"
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
        if any(w in text for w in _SOLO_WORDS):
            draft["team_size"] = 1
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
        out = [t.model_copy(update={"recommended": t.tier == pick}) for t in tiers]
        if r.budget and r.budget < out[0].total_price:
            # 预算连经济版都不够：提示砍功能或分期，不自动压价
            gap = (out[0].total_price - r.budget) / 1_000_000
            note = f"（客户预算比经济版少 {gap:.1f} 万，建议砍掉部分功能或分期）"
            out[0] = out[0].model_copy(update={"summary": out[0].summary + note})
        return out

    @staticmethod
    def _recommend(tiers: list[SolutionTier], budget: int | None) -> str:
        """默认推荐标准版；客户预算放不下标准版时推荐经济版。"""
        by = {t.tier: t for t in tiers}
        if budget and by["standard"].total_price > budget:
            return "economy"
        return "standard"

    def clarify(self, r: SoftwareRequirement) -> dict[str, Any]:
        """需求确认前的粗估：价格区间 + 建议和客户确认的问题。

        低 = 只做客户提到的功能、经济版；高 = 全部功能（含 AI 推断的）、高配版。
        """
        mentioned = [m for m in r.modules if m.source == "mentioned"]
        low_req = r.model_copy(update={"modules": mentioned}) if mentioned else r
        low = min(t.total_price for t in self.configure(low_req))
        high = max(t.total_price for t in self.configure(r))
        return {
            "price_low": low,
            "price_high": high,
            "inferred": len(r.modules) - len(mentioned),
            "questions": (r.questions or default_questions(r))[:5],
        }

    def module_days(self, m: Module) -> int:
        lib = self.params["modules"]
        days = lib.get(m.key, self.params["custom_module"])["days"]
        return int(days[["simple", "medium", "complex"].index(m.complexity)])

    def _build_tier(self, tier_id: str, r: SoftwareRequirement) -> SolutionTier:
        p = self.params
        cfg = p["tiers"][tier_id]
        team = r.team_size or p["team_size"]
        solo = team == 1
        roles = SOLO_ROLES if solo else TEAM_ROLES
        clients = [x for x in r.platforms if x in CLIENT_PLATFORMS]
        if cfg["platforms"] == "first":
            clients = clients[:1]
        platforms = clients + (["admin"] if "admin" in r.platforms else [])
        # 多端：每多一个客户端，模块工作量 × (1 + 系数)；个人全栈用 AI 编码再乘提效系数
        factor = 1 + p["extra_platform_factor"] * max(len(clients) - 1, 0)
        ai_factor = p["solo_ai_factor"] if solo else 1.0

        mods = _dedupe(r.modules)
        if cfg["scope"] == "must":
            mods = [m for m in mods if m.must] or mods

        items: list[BomItem] = [
            self._days("SVC-ARCH", "技术架构与数据库设计", roles["dev"], p["base_days"] * ai_factor)
        ]
        if "admin" in platforms:
            items.append(
                self._days(
                    "SVC-ADMIN", "管理后台基础框架", roles["dev"], p["admin_days"] * ai_factor
                )
            )
        for i, m in enumerate(mods):
            sku = f"MOD-{m.key.upper()}" if m.key != "custom" else f"MOD-CUSTOM-{i + 1}"
            name = f"{m.name}（{COMPLEXITY_NAMES[m.complexity]}）"
            items.append(
                self._days(sku, name, roles["dev"], self.module_days(m) * factor * ai_factor)
            )
        dev_days = sum(i.qty for i in items)
        ratios = {**p["ratios"], **cfg.get("ratios", {})}
        items.insert(
            0,
            self._days(
                "SVC-ANALYSIS", "需求分析与原型设计", roles["pm"], dev_days * ratios["analysis"]
            ),
        )
        if clients:
            items.append(self._days("SVC-UI", "UI 设计", roles["ui"], dev_days * ratios["ui"]))
        items.append(self._days("SVC-QA", "测试与验收", roles["qa"], dev_days * ratios["qa"]))
        if not solo:  # 一个人做不需要单独的项目管理
            items.append(self._days("SVC-PM", "项目管理", roles["pm"], dev_days * ratios["pm"]))
        items.append(
            self._days(
                "SVC-BUFFER", "需求变更与风险预留", roles["dev"], dev_days * ratios["buffer"]
            )
        )
        items.append(self.catalog.line("SVC-DEPLOY", 1))
        if cfg["ops_months"]:
            items.append(self.catalog.line("SVC-OPS", cfg["ops_months"]))
        if cfg["handover"]:
            items.append(self.catalog.line("SVC-HANDOVER", 1))
        items += [self.catalog.line(sku, 1) for sku in third_party_skus(platforms)]

        person_days = sum(i.qty for i in items if i.unit == "人天")
        weeks = math.ceil(person_days / team / 5)
        names = "、".join(PLATFORM_NAMES[x] for x in platforms)
        who = "个人全栈" if solo else f"{team} 人团队"
        summary = f"{len(mods)} 个功能模块 · {names} · 约 {person_days} 人天，{who}约 {weeks} 周"
        if r.deadline_weeks and weeks > r.deadline_weeks:
            advice = "建议分期上线或找人协作" if solo else "需加人或分期"
            summary += f"（比期望工期多 {weeks - r.deadline_weeks} 周，{advice}）"
        ai_monthly = self.ai_monthly_cost(mods)
        if ai_monthly:
            summary += f"；上线后 AI 调用费约 ¥{ai_monthly / 100:,.0f}/月（客户另付）"
        return SolutionTier(
            tier=tier_id,  # type: ignore[arg-type]
            name=TIER_NAMES[tier_id],
            summary=summary,
            items=items,
            specs={
                "delivery": "solo" if solo else "team",
                "team_size": team,
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
                "cost_breakdown": self._cost_breakdown(items),
                "ai_monthly_cost": ai_monthly,
            },
        )

    def _days(self, sku: str, name: str, rate_sku: str, days: float) -> BomItem:
        """按某个角色的人天单价生成一行（人天向上取整，至少 1 天）。

        成本 = 人工成本 + 每人天的 AI 编码工具 / token 分摊（不单列给客户）。
        """
        rate = self.catalog.get(rate_sku)
        return BomItem(
            sku=sku,
            name=name,
            category="service",
            unit="人天",
            qty=max(1, math.ceil(days)),
            unit_cost=rate.cost + int(self.params["ai_tool_cost_per_day"]),
            unit_price=rate.price,
        )

    def _cost_breakdown(self, items: list[BomItem]) -> dict[str, int]:
        """成本构成（分）：人工 / AI 编码工具 / 第三方代采 / 部署运维等服务。"""
        ai_per_day = int(self.params["ai_tool_cost_per_day"])
        days = [i for i in items if i.unit == "人天"]
        ai_tools = sum(i.qty for i in days) * ai_per_day
        third = sum(i.total_cost for i in items if i.sku.startswith("TP-"))
        services = sum(
            i.total_cost for i in items if i.unit != "人天" and not i.sku.startswith("TP-")
        )
        return {
            "labor": sum(i.total_cost for i in days) - ai_tools,
            "ai_tools": ai_tools,
            "third_party": third,
            "services": services,
        }

    def ai_monthly_cost(self, mods: list[Module]) -> int:
        """交付的软件带 AI 功能时，上线后每月的大模型调用费（分，客户承担，不计入报价）。

        调用量和每次 token 数是行业包参数；单价沿用「AI 用量」的输入 / 输出单价，输入输出按 3:1 估。
        """
        if not any(m.key == "ai" for m in mods):
            return 0
        p = self.params
        usage = load_rules().ai_usage
        tokens = p["ai_daily_calls"] * 30 * p["ai_tokens_per_call"]
        yuan = (
            tokens * 0.75 * usage.input_price_per_million
            + tokens * 0.25 * usage.output_price_per_million
        ) / 1_000_000
        return round(yuan * 100)


def default_questions(r: SoftwareRequirement) -> list[str]:
    """没有模型或模型没给问题时的通用确认清单。"""
    qs = []
    inferred = [m.name for m in r.modules if m.source == "inferred"]
    if inferred:
        qs.append(f"这些功能是按常识补充的，客户是否需要：{'、'.join(inferred)}？")
    qs.append("系统有几种使用角色（例如顾客、员工、管理员），各自能做什么？")
    qs.append("是否需要对接已有系统（ERP、财务、OA、支付、硬件设备等）？")
    if not r.deadline_weeks:
        qs.append("期望什么时候上线？能否先上首期核心功能、其余放二期？")
    if not r.budget:
        qs.append("预算大概在什么范围？")
    return qs


def third_party_skus(platforms: list[str]) -> list[str]:
    """上线必需的第三方费用（按成本代采，不赚差价）。"""
    skus = ["TP-CLOUD-1Y", "TP-DOMAIN-SSL"]
    if "mini_program" in platforms:
        skus.append("TP-MP-CERT")
    if "app" in platforms:
        skus.append("TP-APPLE-DEV")
    return skus


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
