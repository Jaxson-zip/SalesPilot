"""规则说明（悬浮提示用）：把 rules.yaml 里的数字整理成「标签 → 值」，前端不写死任何比例和阈值。"""

from pydantic import BaseModel

from app.rules import RuleSet

CATEGORY_LABELS = {
    "hardware": "硬件",
    "software": "软件",
    "service": "服务",
    "passthrough": "代垫费用",
}


class RuleItem(BaseModel):
    label: str
    value: str


class RuleNote(BaseModel):
    title: str
    items: list[RuleItem]
    note: str = ""
    source: str


def _pct(rate: float) -> str:
    return f"{rate * 100:g}%"


def _yuan(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def commission_note(rules: RuleSet) -> RuleNote:
    c = rules.commission
    items = [
        RuleItem(label=f"{CATEGORY_LABELS.get(k, k)}提成", value=_pct(v))
        for k, v in c.rates.items()
    ]
    items.append(
        RuleItem(
            label="低毛利合同",
            value=f"毛利低于 {_pct(c.low_margin_floor)} 时提成 × {c.low_margin_factor:g}",
        )
    )
    return RuleNote(
        title="提成规则",
        items=items,
        note="成交时按合同金额生成「预估提成」，客户回款后按回款比例确认。",
        source="《销售提成制度》· rules.yaml",
    )


def quote_note(rules: RuleSet) -> RuleNote:
    return RuleNote(
        title="报价审批规则",
        items=[
            RuleItem(label="毛利底线", value=f"低于 {_pct(rules.margin.floor_rate)} 需主管审批"),
            RuleItem(label="折扣权限", value=f"超过 {_pct(rules.discount.max_rate)} 需主管审批"),
            RuleItem(label="报价有效期", value=f"{rules.quote.valid_days} 天"),
        ],
        note="毛利和是否需要审批由系统按规则计算，调价后会重新判断。",
        source="《合同审批与回款流程》2.1 · rules.yaml",
    )


def expense_note(rules: RuleSet) -> RuleNote:
    e = rules.expense
    items = [RuleItem(label="客户招待", value=f"人均 {_yuan(e.entertainment_per_person)}")]
    if hotel := e.hotel:
        tier1, other = _yuan(hotel.per_night_tier1), _yuan(hotel.per_night)
        items.append(RuleItem(label="差旅住宿", value=f"一线城市 {tier1}/晚，其他 {other}/晚"))
    items.append(RuleItem(label="差旅交通", value="实报实销"))
    items.append(RuleItem(label="其他费用", value="没有标准，每笔都需主管审批"))
    return RuleNote(
        title="报销标准",
        items=items,
        note="超出标准可以提交，系统会自动转主管审批。",
        source="《费用报销管理制度》· rules.yaml",
    )


class RuleNotes(BaseModel):
    """三类制度说明；固定这三个键，前端按键取用。"""

    commission: RuleNote
    quote: RuleNote
    expense: RuleNote


def rule_notes(rules: RuleSet) -> dict[str, RuleNote]:
    return {
        "commission": commission_note(rules),
        "quote": quote_note(rules),
        "expense": expense_note(rules),
    }
