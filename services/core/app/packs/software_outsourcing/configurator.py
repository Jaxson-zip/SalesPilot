"""软件外包配置器：功能模块拆解 → 估人天 → 经济 / 标准 / 高配三档 → 按角色人天单价定价。

- 拆解（哪些模块、多复杂）由大模型完成，是方案的初稿，销售和客户确认后可以在报价单里改人天；
- 每个模块的人天、各项比例、团队人数都来自 rules.yaml 的 pack 段（管理员可在网页改），
  不让大模型估数字；
- 单价来自产品目录（研发 / UI / 测试 / 产品经理人天，部署、运维、源码交付）。
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.packs.base import (
    TIER_NAMES,
    BomItem,
    Catalog,
    ClientCost,
    SampleSummary,
    SolutionTier,
    price_tier,
    recommend_for_budget,
)
from app.packs.software_outsourcing import drafting
from app.packs.software_outsourcing.budget import fit_budget
from app.packs.software_outsourcing.extras import (
    client_costs,
    default_questions,
    sample_complexity,
    sample_note,
    sample_question,
    third_party_skus,
)
from app.packs.software_outsourcing.requirement import (
    COMPLEXITY_NAMES,
    PLATFORM_NAMES,
    Module,
    SoftwareRequirement,
    dedupe_modules,
)
from app.rules import RuleSet, load_rules
from app.rules.loader import load_raw_rules

PACK_DIR = Path(__file__).parent
CLIENT_PLATFORMS = ("web", "mini_program", "app")
# 各角色用哪个人天单价：团队按角色分开；个人全栈只有一个全栈单价
TEAM_ROLES = {"dev": "DAY-DEV", "ui": "DAY-UI", "qa": "DAY-QA", "pm": "DAY-PM"}
SOLO_ROLES = dict.fromkeys(TEAM_ROLES, "DAY-FULLSTACK")


@dataclass
class _Plan:
    cfg: dict[str, Any]
    team: int
    roles: dict[str, str]
    clients: list[str]
    platforms: list[str]
    mods: list[Module]
    factor: float
    ai_factor: float


@dataclass
class _ClientSide:
    ai_monthly: int
    ocr_pages: int
    client: list[ClientCost]


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
        """给大模型的拆解说明（见 drafting.extract_hint）。"""
        return drafting.extract_hint(self.params["modules"], draft)

    def fill_defaults(self, merged: dict[str, Any]) -> dict[str, Any]:
        """合并上一轮草稿、规则、模型结果之后补默认值。

        拆出了功能但没人说做什么端（模型也偶尔漏填）时默认网站 / H5，而不是回头追问：
        需求卡片上会显示，销售核对时可以改。放在合并之后，不会覆盖上一轮已有的交付端。
        """
        if merged.get("modules") and not merged.get("platforms"):
            return {**merged, "platforms": ["web"]}
        return merged

    def apply_samples(self, merged: dict[str, Any], samples: dict[str, Any]) -> dict[str, Any]:
        """本轮上传了客户样例：记到需求里，并按样例定识别模块的复杂度（没有识别模块就补上）。

        只在上传样例的这一轮调用：之后销售在需求卡片上改了复杂度，不会被样例结果改回去。
        """
        s = SampleSummary.model_validate(samples)
        level = sample_complexity(s)
        mods = [dict(m) for m in merged.get("modules") or []]
        ocr = [m for m in mods if m.get("key") == "ocr"]
        for m in ocr:
            m["complexity"] = level
        if not ocr:
            names = "、".join(t.name for t in s.types[:3])
            mods.append(
                {
                    "key": "ocr",
                    "name": f"单据识别（{names}）" if names else "单据识别",
                    "complexity": level,
                    "must": True,
                    "source": "inferred",
                }
            )
        out = {**merged, "modules": mods, "samples": s.model_dump()}
        return self.fill_defaults(out)

    def draft_requirement(self, text: str) -> dict[str, Any]:
        """规则兜底：按关键词识别端和标准模块（大模型不可用时也能出一版）。"""
        return drafting.rule_draft(self.params["modules"], text)

    # ---------- 配置 ----------

    def configure(self, req: BaseModel, hint: str | None = None) -> list[SolutionTier]:
        r = SoftwareRequirement.model_validate(req.model_dump())
        tiers = [
            price_tier(self._build_tier(t, r), self.rules)
            for t in ("economy", "standard", "premium")
        ]
        fit = self.params["tiers"]["economy"].get("fit_budget")
        if fit and r.budget and tiers[0].total_price > r.budget:
            tiers[0] = fit_budget(r, r.budget, self._economy) or tiers[0]
        out = recommend_for_budget(tiers, r.budget, "建议砍掉部分功能或分期")
        if poc := self.poc(r):
            # 识别准确率是这类项目最大的风险：建议先做样例验证，单独报价，不计入三档
            i = next(i for i, t in enumerate(out) if t.recommended)
            out[i] = out[i].model_copy(update={"summary": out[i].summary + "；" + poc["advice"]})
        return out

    def _economy(self, r: SoftwareRequirement) -> SolutionTier:
        return price_tier(self._build_tier("economy", r), self.rules)

    def clarify(self, r: SoftwareRequirement) -> dict[str, Any]:
        """需求确认前的粗估：价格区间 + 建议和客户确认的问题。

        低 = 只做客户提到的功能、经济版；高 = 全部功能（含 AI 推断的）、高配版。
        """
        mentioned = [m for m in r.modules if m.source == "mentioned"]
        low_req = r.model_copy(update={"modules": mentioned}) if mentioned else r
        low = min(t.total_price for t in self.configure(low_req))
        high = max(t.total_price for t in self.configure(r))
        questions = r.questions or default_questions(r)
        if r.samples and (q := sample_question(r.samples)):
            questions = [q, *questions]
        return {
            "price_low": low,
            "price_high": high,
            "inferred": len(r.modules) - len(mentioned),
            "questions": questions[:5],
            "notes": self.notes(r),
        }

    def notes(self, r: SoftwareRequirement) -> list[str]:
        """粗估时要提醒销售的事：额外的工作量、报价外的费用和建议。"""
        out = []
        if r.samples:
            out.append(sample_note(r.samples))
        if r.no_sop:
            out.append(
                f"客户没有现成的 SOP：报价已含 {self.params['sop_days']} 人天业务调研与流程梳理"
                "（访谈老员工、画流程图、定字段），梳理结果作为验收依据。"
            )
        if poc := self.poc(r):
            out.append(poc["advice"] + "。")
        return out

    def poc(self, r: SoftwareRequirement) -> dict[str, Any] | None:
        """有图片识别时建议先做的样例验证：人天和价格（按研发单价，单独报价）。"""
        if not any(m.key == "ocr" for m in r.modules):
            return None
        days = int(self.params["poc_days"])
        if not days:
            return None
        rate = self.catalog.get("DAY-FULLSTACK" if r.team_size == 1 else "DAY-DEV")
        price = days * rate.price
        which = f"这 {r.samples.total} 张" if r.samples else "客户"
        advice = (
            f"建议先用{which}样例做识别验证（约 {days} 人天 ¥{price / 100:,.0f}，1–2 周）："
            "测出各类单据的识别准确率再签正式合同，验收写明「样例集准确率不低于约定值」"
        )
        return {"days": days, "price": price, "advice": advice}

    def module_days(self, m: Module) -> int:
        lib = self.params["modules"]
        days = lib.get(m.key, self.params["custom_module"])["days"]
        return int(days[["simple", "medium", "complex"].index(m.complexity)])

    def _plan(self, tier_id: str, r: SoftwareRequirement) -> _Plan:
        """这一档做哪些端、哪些模块、几个人做，以及多端 / AI 提效系数。"""
        p = self.params
        cfg = p["tiers"][tier_id]
        team = r.team_size or p["team_size"]
        clients = [x for x in r.platforms if x in CLIENT_PLATFORMS]
        if cfg["platforms"] == "first":
            clients = clients[:1]
        mods = dedupe_modules(r.modules)
        if cfg["scope"] == "must":
            mods = [m for m in mods if m.must] or mods
        return _Plan(
            cfg=cfg,
            team=team,
            roles=SOLO_ROLES if team == 1 else TEAM_ROLES,
            clients=clients,
            platforms=clients + (["admin"] if "admin" in r.platforms else []),
            mods=mods,
            # 多端：每多一个客户端，模块工作量 × (1 + 系数)；个人全栈用 AI 编码再乘提效系数
            factor=1 + p["extra_platform_factor"] * max(len(clients) - 1, 0),
            ai_factor=p["solo_ai_factor"] if team == 1 else 1.0,
        )

    def _dev_items(self, plan: _Plan) -> list[BomItem]:
        p, dev, ai = self.params, plan.roles["dev"], plan.ai_factor
        # 架构要人想清楚，不打 AI 提效折扣；后台框架、功能模块是写代码，按提效系数算
        items = [self._days("SVC-ARCH", "技术架构与数据库设计", dev, p["base_days"])]
        if "admin" in plan.platforms:
            items.append(self._days("SVC-ADMIN", "管理后台基础框架", dev, p["admin_days"] * ai))
        for i, m in enumerate(plan.mods):
            sku = f"MOD-{m.key.upper()}" if m.key != "custom" else f"MOD-CUSTOM-{i + 1}"
            name = f"{m.name}（{COMPLEXITY_NAMES[m.complexity]}）"
            items.append(self._days(sku, name, dev, self.module_days(m) * plan.factor * ai))
        return items

    def _labor_items(self, plan: _Plan, r: SoftwareRequirement) -> list[BomItem]:
        """研发人天 + 按研发人天比例算的分析 / UI / 测试 / 项目管理 / 风险预留。"""
        p, roles = self.params, plan.roles
        items = self._dev_items(plan)
        dev_days = sum(i.qty for i in items)
        ratios = {**p["ratios"], **plan.cfg.get("ratios", {})}
        analysis = dev_days * ratios["analysis"]
        items.insert(0, self._days("SVC-ANALYSIS", "需求分析与原型设计", roles["pm"], analysis))
        if r.no_sop and p["sop_days"]:
            # 没有流程文档：先访谈、梳理，不按研发人天比例算，也不打 AI 提效折扣
            name = "业务调研与 SOP 梳理（访谈、流程图、字段定义）"
            items.insert(1, self._days("SVC-SOP", name, roles["pm"], p["sop_days"]))
        if plan.clients:
            items.append(self._days("SVC-UI", "UI 设计", roles["ui"], dev_days * ratios["ui"]))
        items.append(self._days("SVC-QA", "测试与验收", roles["qa"], dev_days * ratios["qa"]))
        if plan.team != 1:  # 一个人做不需要单独的项目管理
            items.append(self._days("SVC-PM", "项目管理", roles["pm"], dev_days * ratios["pm"]))
        buffer = dev_days * ratios["buffer"]
        items.append(self._days("SVC-BUFFER", "需求变更与风险预留", roles["dev"], buffer))
        return items

    def _service_items(self, plan: _Plan) -> list[BomItem]:
        # 个人交付用个人价（-SOLO），团队价按团队成本定，个人用会远超人天单价
        sfx = "-SOLO" if plan.team == 1 else ""
        items = [self.catalog.line("SVC-DEPLOY" + sfx, 1)]
        if plan.cfg["ops_months"]:
            items.append(self.catalog.line("SVC-OPS" + sfx, plan.cfg["ops_months"]))
        if plan.cfg["handover"]:
            items.append(self.catalog.line("SVC-HANDOVER" + sfx, 1))
        return items

    def _summary(
        self, plan: _Plan, r: SoftwareRequirement, days: int, weeks: int, costs: _ClientSide
    ) -> str:
        names = "、".join(PLATFORM_NAMES[x] for x in plan.platforms)
        solo = plan.team == 1
        who = "个人全栈" if solo else f"{plan.team} 人团队"
        out = f"{len(plan.mods)} 个功能模块 · {names} · 约 {days} 人天，{who}约 {weeks} 周"
        if r.deadline_weeks and weeks > r.deadline_weeks:
            advice = "建议分期上线或找人协作" if solo else "需加人或分期"
            out += f"（比期望工期多 {weeks - r.deadline_weeks} 周，{advice}）"
        if costs.ai_monthly:
            basis = f"，其中图片识别按每月 {costs.ocr_pages:,} 张估" if costs.ocr_pages else ""
            out += f"；上线后 AI 调用费约 ¥{costs.ai_monthly / 100:,.0f}/月（客户另付{basis}）"
        yearly = sum(c.amount for c in costs.client if c.period == "year")
        if yearly:
            out += f"；云服务器、域名等第三方费用约 ¥{yearly / 100:,.0f}/年由客户自付"
        return out

    def _build_tier(self, tier_id: str, r: SoftwareRequirement) -> SolutionTier:
        plan = self._plan(tier_id, r)
        items = self._labor_items(plan, r) + self._service_items(plan)
        third = [self.catalog.line(sku, 1) for sku in third_party_skus(plan.platforms)]
        in_quote = bool(self.params.get("third_party_in_quote"))
        if in_quote:
            items += third
        days = sum(i.qty for i in items if i.unit == "人天")
        weeks = math.ceil(days / plan.team / 5)
        ai_monthly, ocr_pages = self.ai_monthly_cost(plan.mods, r.ocr_monthly_pages)
        client = client_costs([] if in_quote else third, ai_monthly, ocr_pages)
        costs = _ClientSide(ai_monthly=ai_monthly, ocr_pages=ocr_pages, client=client)
        modules = [
            {
                "name": m.name,
                "complexity": m.complexity,
                "must": m.must,
                "days": self.module_days(m),
            }
            for m in plan.mods
        ]
        return SolutionTier(
            tier=tier_id,  # type: ignore[arg-type]
            name=TIER_NAMES[tier_id],
            summary=self._summary(plan, r, days, weeks, costs),
            items=items,
            specs={
                "delivery": "team" if plan.team != 1 else "solo",
                "team_size": plan.team,
                "platforms": plan.platforms,
                "modules": modules,
                "person_days": days,
                "weeks": weeks,
                "cost_breakdown": self._cost_breakdown(items),
                "ai_monthly_cost": ai_monthly,
                "ocr_monthly_pages": ocr_pages,
                # 运营期客户自付费用（实报实销，不含在报价内）
                "client_costs": [c.model_dump() for c in client],
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

    def ai_monthly_cost(self, mods: list[Module], ocr_pages: int | None = None) -> tuple[int, int]:
        """交付的软件带 AI 功能时，上线后每月的大模型调用费（分，客户承担，不计入报价）。

        - 对话类（key=ai）：日调用量 × 每次 token 数，单价沿用「AI 用量」，输入输出按 3:1 估；
        - 图片识别（key=ocr）：每月张数 × 每张费用；客户没说量时按默认月量估。
        返回（月费，按多少张估的识别量；没有识别为 0）。
        """
        p = self.params
        keys = {m.key for m in mods}
        cost = 0.0
        if "ai" in keys:
            usage = load_rules().ai_usage
            tokens = p["ai_daily_calls"] * 30 * p["ai_tokens_per_call"]
            yuan = (
                tokens * 0.75 * usage.input_price_per_million
                + tokens * 0.25 * usage.output_price_per_million
            ) / 1_000_000
            cost += yuan * 100
        pages = 0
        if "ocr" in keys:
            pages = ocr_pages if ocr_pages is not None else int(p["ocr_monthly_pages"])
            cost += pages * p["ocr_cost_per_page"]
        return round(cost), pages


def create_configurator() -> SoftwareOutsourcingConfigurator:
    return SoftwareOutsourcingConfigurator()
