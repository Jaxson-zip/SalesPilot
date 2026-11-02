"""给模型看的商机阶段：工具结果里 stage 是英文代码，旁边附上系统里的中文名，模型照抄、不自己翻译。

回归：管理员问业绩时，模型把 proposal / negotiation 说成「提案阶段」「谈判中」，和页面上的
「方案报价」「商务谈判」对不上。
"""

from typing import Any

from app.crm.schemas.opportunity import STAGE_LABELS

_STAGE_KEYS = {"stage", "from_stage", "to_stage"}


def annotate_stages(value: Any) -> Any:
    """递归给阶段字段加 `<字段>_label`（只认 STAGE_LABELS 里的代码，其他值原样保留）。"""
    if isinstance(value, list):
        return [annotate_stages(v) for v in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, v in value.items():
        out[key] = annotate_stages(v)
        if key in _STAGE_KEYS and isinstance(v, str) and v in STAGE_LABELS:
            out[f"{key}_label"] = STAGE_LABELS[v]
    return out
