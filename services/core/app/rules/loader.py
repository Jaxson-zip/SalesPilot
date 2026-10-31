"""读取 rules.yaml，支持行业包规则覆盖（深度合并）。"""

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from app.rules import overrides

RULES_FILE = Path(__file__).with_name("rules.yaml")


class MarginRules(BaseModel):
    floor_rate: float


class DiscountRules(BaseModel):
    max_rate: float


class CommissionRules(BaseModel):
    rates: dict[str, float]
    low_margin_floor: float
    low_margin_factor: float


class HotelRules(BaseModel):
    per_night: int
    per_night_tier1: int
    tier1_cities: list[str] = []
    rule_ref: str = ""

    def limit_for(self, city: str) -> int:
        """城市名包含一线城市名（如「深圳市南山区」）即按一线标准。"""
        tier1 = any(c in city for c in self.tier1_cities)
        return self.per_night_tier1 if tier1 else self.per_night


class ExpenseRules(BaseModel):
    entertainment_per_person: int
    rule_ref: str = ""
    required_kinds: dict[str, list[str]] = {"default": ["invoice"]}
    hotel: HotelRules | None = None

    def kinds_for(self, expense_type: str) -> list[str]:
        return self.required_kinds.get(expense_type, self.required_kinds.get("default", []))


class AttachmentRules(BaseModel):
    max_bytes: int = 10 * 1024 * 1024
    allowed_types: list[str] = ["image/jpeg", "image/png", "application/pdf"]


class AgentRules(BaseModel):
    margin_max_retries: int
    max_tool_calls: int


class PipelineRules(BaseModel):
    stage_win_rate: dict[str, int] = {
        "lead": 10,
        "qualified": 25,
        "proposal": 50,
        "negotiation": 75,
        "won": 100,
        "lost": 0,
    }
    stale_days: int = 14


class PaymentStage(BaseModel):
    name: str
    ratio: float
    due_days: int


class PaymentRules(BaseModel):
    schedule: list[PaymentStage] = [
        PaymentStage(name="预付款", ratio=0.3, due_days=0),
        PaymentStage(name="到货验收款", ratio=0.6, due_days=60),
        PaymentStage(name="质保金", ratio=0.1, due_days=425),
    ]
    remind_days: int = 3
    followup_days: int = 30
    block_days: int = 90
    rule_ref: str = ""


class OrgRules(BaseModel):
    solo_mode: bool = False


class QuoteRules(BaseModel):
    valid_days: int = 30
    followup_days: int = 3


class PrivacyRules(BaseModel):
    """客户数据防泄漏：电话默认脱敏、查看留痕并限次；导出按角色授权、限条数。"""

    phone_reveal_daily_limit: int = 30
    export_max_rows: int = 200
    export_roles: dict[str, list[str]] = {
        "customers": ["manager", "admin"],
        "opportunities": ["manager", "admin"],
        "quotes": ["sales", "manager", "admin"],
        "contracts": ["manager", "admin"],
        "expenses": ["sales", "manager", "admin"],
    }


class MeddicRules(BaseModel):
    """各阶段应该已经确认的 MEDDIC 要素（进入该阶段还没确认 → 商机上提示风险）。"""

    stage_required: dict[str, list[str]] = {
        "qualified": ["identify_pain"],
        "proposal": ["metrics", "decision_criteria"],
        "negotiation": ["economic_buyer", "decision_process", "champion"],
    }


class AiUsageRules(BaseModel):
    """AI 成本估算：按 token 单价（元 / 百万 tokens）；预算只做提醒，每人每日额度会拦截。"""

    input_price_per_million: float = 2.0
    output_price_per_million: float = 8.0
    monthly_budget: int = 50_000  # 全公司每月预算（分），0 表示不设
    team_monthly_budget: int = 0  # 每个团队每月预算（分），0 表示不设
    user_daily_tokens: int = 2_000_000  # 每人每天 tokens 上限，超过后当天不能再发起 AI 调用；0 不限


class RuleSet(BaseModel):
    org: OrgRules = OrgRules()
    margin: MarginRules
    discount: DiscountRules
    commission: CommissionRules
    expense: ExpenseRules
    attachment: AttachmentRules = AttachmentRules()
    agent: AgentRules
    pipeline: PipelineRules = PipelineRules()
    quote: QuoteRules = QuoteRules()
    payment: PaymentRules = PaymentRules()
    privacy: PrivacyRules = PrivacyRules()
    meddic: MeddicRules = MeddicRules()
    ai_usage: AiUsageRules = AiUsageRules()


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


@lru_cache
def _base_rules() -> dict[str, Any]:
    return read_yaml(RULES_FILE)


def load_raw_rules(override_file: Path | None = None, scope: str | None = None) -> dict[str, Any]:
    """合并后的原始规则字典（含行业包专属的 pack 段）。

    合并顺序：通用 rules.yaml → 网页上改过的通用规则 → 行业包 rules.yaml → 网页上改过的行业包参数。
    scope 是行业包 id（取该行业包在网页上的改动）。
    """
    raw = deep_merge(copy.deepcopy(_base_rules()), overrides.nested(overrides.GLOBAL))
    if override_file is not None:
        raw = deep_merge(raw, read_yaml(override_file))
    if scope:
        pack = overrides.nested(scope)
        pack.pop("catalog", None)  # 产品价格的改动由 Catalog 合并
        raw = deep_merge(raw, pack)
    return raw


def load_rules(override_file: Path | None = None, scope: str | None = None) -> RuleSet:
    """加载规则；传入行业包 rules.yaml（及行业包 id）时用其覆盖同名项。"""
    return RuleSet.model_validate(load_raw_rules(override_file, scope))


def solo_mode() -> bool:
    """个人模式（一个人接单）：审批自动通过、主管可以改系统配置。"""
    return load_rules().org.solo_mode
