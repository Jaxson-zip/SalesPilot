"""读取 rules.yaml，支持行业包规则覆盖（深度合并）。"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

RULES_FILE = Path(__file__).with_name("rules.yaml")


class MarginRules(BaseModel):
    floor_rate: float


class DiscountRules(BaseModel):
    max_rate: float


class CommissionRules(BaseModel):
    rates: dict[str, float]
    low_margin_floor: float
    low_margin_factor: float


class ExpenseRules(BaseModel):
    entertainment_per_person: int


class AgentRules(BaseModel):
    margin_max_retries: int
    max_tool_calls: int


class RuleSet(BaseModel):
    margin: MarginRules
    discount: DiscountRules
    commission: CommissionRules
    expense: ExpenseRules
    agent: AgentRules


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


def load_rules(override_file: Path | None = None) -> RuleSet:
    """加载通用规则；传入行业包 rules.yaml 时用其覆盖同名项。"""
    raw = _base_rules()
    if override_file is not None:
        raw = deep_merge(raw, read_yaml(override_file))
    return RuleSet.model_validate(raw)
