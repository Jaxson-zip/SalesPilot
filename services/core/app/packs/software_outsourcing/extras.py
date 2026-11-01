"""报价之外的部分：粗估时给销售的提醒、建议和客户确认的问题、运营期客户自付的费用。

金额都来自产品目录和规则参数，这里只做汇总和措辞。
"""

from app.packs.base import BomItem, ClientCost, SampleSummary
from app.packs.software_outsourcing.requirement import COMPLEXITY_NAMES, SoftwareRequirement


def sample_complexity(s: SampleSummary) -> str:
    """按样例定识别难度：3 类以上单据或手写占两成以上算复杂，2 类或模糊多算中等。"""
    n = max(s.analyzed, 1)
    if len(s.types) >= 3 or s.handwritten / n >= 0.2:
        return "complex"
    if len(s.types) == 2 or s.blurry / n >= 0.2:
        return "medium"
    return "simple"


def sample_note(s: SampleSummary) -> str:
    types = "、".join(f"{t.name} {t.count}" for t in s.types)
    failed = f"，{s.total - s.analyzed} 张没识别出来" if s.total > s.analyzed else ""
    quality = f"；模糊 {s.blurry} 张、手写 {s.handwritten} 张" if s.blurry or s.handwritten else ""
    level = COMPLEXITY_NAMES[sample_complexity(s)]
    return (
        f"样例分析：{s.total} 张里识别出 {len(s.types)} 类单据（{types}）{failed}{quality}。"
        f"按样例，单据识别建议按「{level}」估。"
    )


def sample_question(s: SampleSummary) -> str | None:
    """让客户确认样例里识别出的字段是不是要录入的全部字段（列最多的一类）。"""
    top = next((t for t in s.types if t.fields), None)
    if not top:
        return None
    fields = "、".join(top.fields[:6]) + ("等" if len(top.fields) > 6 else "")
    more = f"其余 {len(s.types) - 1} 类单据也请确认一下。" if len(s.types) > 1 else ""
    return f"样例里{top.name}识别出的字段有 {fields}，是否就是要录入系统的全部字段？{more}"


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


def client_costs(third: list[BomItem], ai_monthly: int, ocr_pages: int) -> list[ClientCost]:
    """运营期客户自付费用：没计入报价的第三方费用（按年）+ 上线后的大模型调用费（按月）。"""
    out = [
        ClientCost(
            name=i.name.split("（")[0],
            amount=i.unit_price,
            period="year",
            note="以客户主体开通" if "客户主体" in i.name else "按实际采购价，可由我方代办",
        )
        for i in third
    ]
    if ai_monthly:
        basis = f"，其中图片识别按每月 {ocr_pages:,} 张估" if ocr_pages else ""
        out.append(
            ClientCost(
                name="大模型调用费（AI 功能）",
                amount=ai_monthly,
                period="month",
                note=f"按预计调用量估算，以实际用量为准{basis}",
            )
        )
    return out


def third_party_skus(platforms: list[str]) -> list[str]:
    """上线必需的第三方费用（按成本代采，不赚差价）。"""
    skus = ["TP-CLOUD-1Y", "TP-DOMAIN-SSL"]
    if "mini_program" in platforms:
        skus.append("TP-MP-CERT")
    if "app" in platforms:
        skus.append("TP-APPLE-DEV")
    return skus
