"""审批建议（审查 v6 #15）：按这张单据的实际情况给主管提示，不再是同一句模板话。

规则代码生成（不调用模型），所以界面上叫「审批建议」而不是「AI 建议」。考虑：
- 客户等级：A 级（重点客户）可酌情通过；B / C 级倾向按标准处理
- 申请人本月已有几次超标 / 低毛利审批：多次时提醒
- 报价：低毛利时按毛利差额、折扣超权限时按折扣给出核对方向

建议在提交时存进审批单；关联商机的当前状态由 deal_notes 在列表里实时给出。
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crm.models import Approval, Customer, Expense, Opportunity, Quote
from app.crm.schemas.opportunity import FINAL_STAGES, STAGE_LABELS
from app.crm.services.codes import local_today, month_start

LEVEL_TEXT = {"A": "A 级重点客户", "B": "B 级客户", "C": "C 级客户"}


def _level(db: Session, customer_id: uuid.UUID | None) -> str | None:
    if customer_id is None:
        return None
    customer = db.get(Customer, customer_id)
    return customer.level if customer else None


def _month_count(db: Session, target_type: str, owner_id: uuid.UUID | None) -> int:
    """申请人本月已有的同类审批数（不含正在创建的这一条）。"""
    stmt = select(func.count()).where(
        Approval.target_type == target_type,
        Approval.owner_id == owner_id,
        Approval.created_at >= month_start(),
    )
    return int(db.scalar(stmt) or 0)


def expense_hint(
    db: Session, customer_id: uuid.UUID | None, owner_id: uuid.UUID | None, over_amount: int
) -> str:
    level = _level(db, customer_id)
    times = _month_count(db, "expense", owner_id)
    parts = [f"超出标准 ¥{over_amount / 100:,.0f}"]
    if level == "A":
        parts.append(f"{LEVEL_TEXT['A']}，若是关键节点（方案汇报、签约前）可酌情通过")
    elif level:
        parts.append(f"{LEVEL_TEXT[level]}，建议超出部分由个人承担")
    else:
        parts.append("未关联客户，建议核实招待对象")
    if times >= 2:
        parts.append(f"申请人本月已是第 {times + 1} 次超标，建议提醒按标准安排")
    elif times == 0:
        parts.append("申请人本月首次超标")
    return "；".join(parts) + "。"


def quote_hint(
    db: Session,
    customer_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    reasons: list[str],
    margin_gap: float | None,
) -> str:
    level = _level(db, customer_id)
    times = _month_count(db, "quote", owner_id)
    parts: list[str] = []
    if margin_gap is not None and margin_gap > 0:
        parts.append(
            f"毛利比底线低 {margin_gap * 100:.1f} 个百分点，"
            "可先核对能否换用低成本配置或减少服务人天"
        )
    if any("折扣" in r for r in reasons):
        parts.append("折扣超出销售权限，确认是否有竞品压价或长期合作承诺")
    if level == "A":
        parts.append(f"{LEVEL_TEXT['A']}，战略价值高时可酌情通过")
    elif level:
        parts.append(f"{LEVEL_TEXT[level]}，建议坚持价格底线")
    if times >= 2:
        parts.append(f"申请人本月已有 {times} 张报价进入审批")
    return "；".join(parts or reasons) + "。"


def deal_notes(db: Session, targets: Iterable[Quote | Expense]) -> dict[uuid.UUID, str]:
    """审批单关联商机的当前状态（按目标 id）。审批建议是提交时写的，商机之后可能已输单 / 赢单。"""
    by_target = {t.id: t.opportunity_id for t in targets if t.opportunity_id}
    if not by_target:
        return {}
    stmt = select(Opportunity).where(Opportunity.id.in_(set(by_target.values())))
    opps = {o.id: o for o in db.scalars(stmt)}
    notes: dict[uuid.UUID, str] = {}
    for target_id, opp_id in by_target.items():
        opp = opps.get(opp_id)
        if opp is not None:
            notes[target_id] = _deal_note(opp)
    return notes


def _deal_note(opp: Opportunity) -> str:
    if opp.stage not in FINAL_STAGES:
        return f"关联商机「{opp.name}」当前处于{STAGE_LABELS[opp.stage]}阶段"
    when = f"已于 {local_today(opp.closed_at):%m-%d} " if opp.closed_at else "已"
    return f"关联商机「{opp.name}」{when}{STAGE_LABELS[opp.stage]}，审批建议是提交时的判断"
