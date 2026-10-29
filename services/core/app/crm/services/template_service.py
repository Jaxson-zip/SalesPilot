"""业务模板（GET /api/templates）：读取 rules/templates.yaml，占位符用 rules.yaml 计算后填入。

模板只放文案，数字一律来自规则（AGENTS 第 5 条），改了报销标准，模板里的说明会跟着变。
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.crm.schemas.finance import EXPENSE_TYPE_LABELS, ExpenseType, TransportMode
from app.crm.schemas.task import TaskType
from app.crm.services.rule_notes import RuleNotes, rule_notes
from app.rules import RuleSet, load_rules
from app.rules.loader import read_yaml

TEMPLATES_FILE = Path(__file__).resolve().parents[2] / "rules" / "templates.yaml"
KIND_LABELS = {"invoice": "发票", "receipt": "小票", "other": "其他票据"}
Role = Literal["sales", "manager", "admin"]


class ExpenseTemplate(BaseModel):
    id: str
    label: str
    type: ExpenseType
    transport_mode: TransportMode | None = None
    reason: str = ""
    example: str = ""


class ExpenseGuide(BaseModel):
    type: ExpenseType
    label: str
    standard: str
    must: str
    attachments: list[str]
    rule_ref: str


class FollowupTemplate(BaseModel):
    id: str
    label: str
    type: Literal["phone", "visit", "wechat"]
    content: str


class TaskTemplate(BaseModel):
    type: TaskType
    title: str


class PromptTemplate(BaseModel):
    title: str
    prompt: str


class Templates(BaseModel):
    expense_templates: list[ExpenseTemplate]
    expense_guides: list[ExpenseGuide]
    followup: list[FollowupTemplate]
    task: list[TaskTemplate]
    lost_reasons: list[str]
    quote_terms: list[str]
    contract_terms: list[str]  # 合同要素确认单的说明
    ai_prompts: list[PromptTemplate]
    # 规则说明（悬浮提示）：commission / quote / expense，数字来自 rules.yaml
    rule_notes: RuleNotes


class _Values(dict[str, str]):
    """缺少的占位符原样保留（例如没有配置住宿标准时），不让整个接口报错。"""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _fill(text: Any, values: dict[str, str]) -> str:
    return str(text).format_map(_Values(values))


def _yuan(fen: int) -> str:
    return f"{fen / 100:.0f}"


def _placeholders(rules: RuleSet) -> dict[str, str]:
    values = {
        "per_person": _yuan(rules.expense.entertainment_per_person),
        "valid_days": str(rules.quote.valid_days),
    }
    if hotel := rules.expense.hotel:
        values |= {
            "per_night": _yuan(hotel.per_night),
            "per_night_tier1": _yuan(hotel.per_night_tier1),
            "tier1_cities": "、".join(hotel.tier1_cities),
        }
    return values


def _guides(raw: dict[str, Any], rules: RuleSet, values: dict[str, str]) -> list[ExpenseGuide]:
    refs = {
        "entertainment": rules.expense.rule_ref,
        "hotel": rules.expense.hotel.rule_ref if rules.expense.hotel else "",
    }
    return [
        ExpenseGuide(
            type=t,
            label=EXPENSE_TYPE_LABELS[t],
            standard=_fill(g.get("standard", ""), values),
            must=str(g.get("must", "")),
            attachments=[KIND_LABELS.get(k, k) for k in rules.expense.kinds_for(t)],
            rule_ref=refs.get(t) or "《费用报销管理制度》",
        )
        for t, g in raw.items()
    ]


@lru_cache
def _raw() -> dict[str, Any]:
    return read_yaml(TEMPLATES_FILE)


def get_templates(role: Role) -> Templates:
    raw, rules = _raw(), load_rules()
    values = _placeholders(rules)
    expense = raw.get("expense", {})
    return Templates(
        expense_templates=[ExpenseTemplate.model_validate(t) for t in expense.get("templates", [])],
        expense_guides=_guides(expense.get("guides", {}), rules, values),
        followup=[FollowupTemplate.model_validate(t) for t in raw.get("followup", [])],
        task=[TaskTemplate.model_validate(t) for t in raw.get("task", [])],
        lost_reasons=[str(r) for r in raw.get("lost_reasons", [])],
        quote_terms=[str(t).format(**values) for t in raw.get("quote_terms", [])],
        contract_terms=[str(t).format(**values) for t in raw.get("contract_terms", [])],
        rule_notes=RuleNotes.model_validate(rule_notes(rules)),
        ai_prompts=[
            PromptTemplate.model_validate(p) for p in raw.get("ai_prompts", {}).get(role, [])
        ],
    )
