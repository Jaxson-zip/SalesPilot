"""给模型看的金额：工具结果里的金额字段是「分」，旁边附上换算好的文字，模型直接引用、不自己换算。

回归：商机金额 46000000 分 = ¥460,000 = 46 万元，模型自己换算说成了「460 万元」。
"""

import re
from typing import Any

# 字段名以这些词结尾的整数都是「分」：amount / total_price / unit_cost / annual_budget /
# estimated_commission_month 等；total、paid 这类可能是数量的不算
_MONEY_KEY = re.compile(r"(^|_)(amount|price|cost|commission|budget|balance)(_month)?$")
_MONEY_EXTRA = {"estimated", "confirmed"}  # 提成预估 / 已确认


def is_money_key(key: str) -> bool:
    return key in _MONEY_EXTRA or bool(_MONEY_KEY.search(key))


def _trim(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def yuan_text(fen: int) -> str:
    """46000000 → ¥460,000（46 万元）；不足 1 万元不加万元；负数写成 -¥100。"""
    yuan = abs(fen) / 100
    text = f"{'-' if fen < 0 else ''}¥{_trim(yuan)}"
    if yuan >= 10_000:
        text += f"（{'-' if fen < 0 else ''}{_trim(yuan / 10_000)} 万元）"
    return text


def annotate_money(value: Any) -> Any:
    """递归给金额字段加 `<字段>_text`；原来的分值保留（调用工具时参数仍按分传）。"""
    if isinstance(value, list):
        return [annotate_money(v) for v in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, v in value.items():
        out[key] = annotate_money(v)
        if (
            isinstance(key, str)
            and isinstance(v, int)
            and not isinstance(v, bool)
            and is_money_key(key)
        ):
            out[f"{key}_text"] = yuan_text(v)
    return out
