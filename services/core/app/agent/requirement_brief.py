"""对话循环里的「方案进行中」说明：告诉模型方案走到哪一步、需求草稿里已经有什么。

回归：需求卡片已经发出（等销售确认），用户再说一句「不是电脑采购，是软件开发」，
模型只知道「有需求草稿」，于是说「上一轮还没有真正生成方案」，又问了一遍已经说过的管理后台。
字段名和说明取自行业包的需求模型，不在这里写行业相关的内容。
"""

from typing import Any

from app.agent.money import yuan_text
from app.common.errors import BizError
from app.packs.registry import get_configurator, get_pack

ROOT_MISSING_LABEL = "具体要做什么、规模多大"
_SKIP = {"questions", "samples"}  # 待确认问题、样例汇总不算「已经给过的信息」


def _label(name: str, description: str | None) -> str:
    text = (description or name).replace("（分）", "")
    return text.split("：")[0].split("，")[0].strip()


def _value(name: str, value: Any) -> str | None:
    if value in (None, "", [], {}) or value is False:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and name == "budget":
        return yuan_text(value)
    if isinstance(value, list):
        parts = [str(v.get("name", v)) if isinstance(v, dict) else str(v) for v in value]
        return "、".join(parts)
    return str(value)


def requirement_facts(pack_id: str | None, requirement: dict[str, Any]) -> list[str]:
    """需求草稿里已经有的信息，一行一项（「功能模块拆解清单：在线预约、订单查询」）。"""
    try:
        fields = get_configurator(pack_id or "").requirement_model.model_fields
    except BizError:
        return []
    out = []
    for name, field in fields.items():
        value = _value(name, requirement.get(name))
        if name not in _SKIP and value is not None:
            out.append(f"- {_label(name, field.description)}：{value}")
    return out


def solution_progress(pack_id: str | None, requirement: dict[str, Any], confirmed: bool) -> str:
    """有需求草稿时给模型的说明：现在在哪一步、已有哪些信息、用户纠正方向时怎么回。"""
    try:
        pack = get_pack(pack_id or "").name
    except BizError:
        pack = "当前行业包"
    stage = (
        "需求已经确认，三档方案已经按它算过。"
        if confirmed
        else f"上一轮已经按「{pack}」拆好需求清单（下方需求卡片）并给了粗估区间，"
        "等销售在卡片上核对后点「确认需求，出报价」生成三档正式报价。方案已经在进行，"
        "不要说「还没有生成方案」。"
    )
    facts = "\n".join(requirement_facts(pack_id, requirement))
    return (
        f"## 方案进行中\n{stage}\n需求草稿里已经有这些信息，不要再问：\n{facts}\n"
        "用户这句话如果是在补充或修改需求（功能模块、端、预算、工期、人数、模型、并发等），"
        f"调用 start_solution。用户只是纠正方向（例如「不是电脑采购，是软件开发」）时，"
        f"简短确认现在就是按「{pack}」处理，再提示在需求卡片上核对；不要重复上一轮已经问过的问题。"
    )


def missing_labels(
    pack_id: str | None, missing: list[str], invalid: dict[str, str] | None = None
) -> list[str]:
    """追问字段的中文说明（取需求模型字段的 description）。

    整体校验（__root__）用需求模型的 missing_hint，没有时用通用说法；不认识的字段名不外露。
    """
    try:
        model = get_configurator(pack_id or "").requirement_model
    except Exception:
        model = None
    fields = model.model_fields if model else {}
    root = getattr(model, "missing_hint", None) or ROOT_MISSING_LABEL
    labels = [(fields[f].description or root) if f in fields else root for f in missing]
    # 填了但不合理的字段带上原因，别像没听到用户说的数
    labels = [
        f"{label}（{(invalid or {})[f]}）" if f in (invalid or {}) else label
        for f, label in zip(missing, labels, strict=True)
    ]
    return list(dict.fromkeys(labels))
