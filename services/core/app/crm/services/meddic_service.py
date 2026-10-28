"""MEDDIC 赢单辅导：每个商机 6 项（量化收益、经济决策人、决策标准、决策流程、痛点、内部支持者）。

- 销售手动标状态（已确认 / 待验证 / 缺失）并写证据；
- 「AI 评估」读跟进记录和联系人，给出每项的状态、证据和下一步该问的问题（只是建议，采纳后才保存）；
  没有可用模型时按关键词规则给出初步判断；
- 按阶段提示风险：例如进入商务谈判还没确认经济决策人（rules.meddic.stage_required）。
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.models import Contact, Followup, Opportunity
from app.crm.schemas.dashboard import CONTACT_ROLE_LABELS
from app.crm.schemas.opportunity import STAGE_LABELS
from app.crm.services import activity_service
from app.crm.services import opportunity_service as opp_service
from app.rules import load_rules

logger = logging.getLogger("core.meddic")

MeddicKey = Literal[
    "metrics",
    "economic_buyer",
    "decision_criteria",
    "decision_process",
    "identify_pain",
    "champion",
]
MeddicStatus = Literal["confirmed", "partial", "missing"]

# key → (中文名, 说明, 建议问题)
ITEMS: dict[str, tuple[str, str, list[str]]] = {
    "identify_pain": (
        "痛点",
        "客户不解决就会有损失的业务问题",
        [
            "现在这件事靠什么方式在做？最头疼的环节是哪一步？",
            "如果今年不解决，会影响到哪些业务指标？",
        ],
    ),
    "metrics": (
        "量化收益",
        "客户认可的、能用数字衡量的收益",
        [
            "上线后希望节省多少人力 / 时间？怎么衡量算成功？",
            "这个项目在内部汇报时用什么指标说明价值？",
        ],
    ),
    "economic_buyer": (
        "经济决策人",
        "最终批预算、能拍板的人，以及我们是否见过",
        ["这个项目的预算最后由谁审批？", "方案汇报时能否请拍板的领导一起参加？"],
    ),
    "decision_criteria": (
        "决策标准",
        "客户选型看重什么：性能、价格、国产化、交付周期等",
        [
            "选型时最看重哪三点？有没有硬性要求（国产化、私有化）？",
            "会和哪几家对比？对比时看什么？",
        ],
    ),
    "decision_process": (
        "决策流程",
        "从立项、测试、招标到签约的步骤和时间点",
        ["从现在到签合同要经过哪几步？谁参与？", "需要走招标吗？预计什么时候立项 / 招标？"],
    ),
    "champion": (
        "内部支持者",
        "在客户内部认可我们、愿意替我们推动的人",
        ["内部谁最希望这个项目落地？", "能否请他帮忙引荐决策人、分享内部的评估进展？"],
    ),
}
ORDER: list[str] = list(ITEMS)
STATUS_SCORE = {"confirmed": 1.0, "partial": 0.5, "missing": 0.0}
_STAGE_ORDER = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]


class MeddicItem(BaseModel):
    key: MeddicKey
    label: str
    hint: str
    status: MeddicStatus = "missing"
    evidence: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None
    questions: list[str] = Field(default_factory=list)  # 未确认时：下一步该问的问题
    required: bool = False  # 当前阶段按规则应该已经确认
    risk: bool = False  # required 但还没确认


class MeddicOut(BaseModel):
    opportunity_id: uuid.UUID
    stage: str
    score: int  # 0–100
    items: list[MeddicItem]
    gaps: list[str]  # 未确认项的中文名
    risks: list[str]  # 当前阶段应确认却没确认的项


class MeddicPatch(BaseModel):
    status: MeddicStatus
    evidence: str | None = Field(default=None, max_length=500)


class MeddicUpdate(BaseModel):
    items: dict[MeddicKey, MeddicPatch]


class Suggestion(BaseModel):
    key: MeddicKey
    status: MeddicStatus
    evidence: str | None = Field(default=None, max_length=500)


class MeddicAssessment(BaseModel):
    """AI 对 MEDDIC 各项的判断（只是建议，用户采纳后才保存）。"""

    items: list[Suggestion]
    summary: str = Field(default="", max_length=500, description="一句话：最大的缺口和下一步")


class AssessOut(BaseModel):
    source: Literal["ai", "rule"]
    summary: str
    items: list[Suggestion]


def required_keys(stage: str) -> set[str]:
    """当前阶段及之前阶段要求确认的项（规则可在 rules.yaml 调整）。"""
    req = load_rules().meddic.stage_required
    idx = _STAGE_ORDER.index(stage) if stage in _STAGE_ORDER else 0
    keys: set[str] = set()
    for s in _STAGE_ORDER[: idx + 1]:
        keys.update(req.get(s, []))
    return keys


def to_out(opp: Opportunity) -> MeddicOut:
    saved: dict[str, Any] = dict(opp.meddic or {})
    required = required_keys(opp.stage) if opp.stage not in ("won", "lost") else set()
    items: list[MeddicItem] = []
    for key in ORDER:
        label, hint, questions = ITEMS[key]
        raw = saved.get(key) or {}
        status = raw.get("status", "missing")
        item = MeddicItem(
            key=key,  # type: ignore[arg-type]
            label=label,
            hint=hint,
            status=status,
            evidence=raw.get("evidence"),
            updated_at=raw.get("updated_at"),
            updated_by=raw.get("updated_by"),
            questions=[] if status == "confirmed" else questions,
            required=key in required,
            risk=key in required and status != "confirmed",
        )
        items.append(item)
    score = round(100 * sum(STATUS_SCORE[i.status] for i in items) / len(items))
    return MeddicOut(
        opportunity_id=opp.id,
        stage=opp.stage,
        score=score,
        items=items,
        gaps=[i.label for i in items if i.status != "confirmed"],
        risks=[i.label for i in items if i.risk],
    )


def get_meddic(db: Session, user: CurrentUser, opportunity_id: uuid.UUID) -> MeddicOut:
    return to_out(opp_service.get_opportunity(db, user, opportunity_id))


def update_meddic(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID, body: MeddicUpdate
) -> MeddicOut:
    """只有负责人本人可以修改；记一条商机动态。"""
    opp = opp_service.get_owned(db, user, opportunity_id)
    saved = dict(opp.meddic or {})
    now = datetime.now(UTC).isoformat()
    changed: list[str] = []
    for key, patch in body.items.items():
        old = saved.get(key) or {}
        if old.get("status") == patch.status and old.get("evidence") == patch.evidence:
            continue
        saved[key] = {
            "status": patch.status,
            "evidence": (patch.evidence or "").strip() or None,
            "updated_at": now,
            "updated_by": user.name,
        }
        changed.append(ITEMS[key][0])
    if changed:
        opp.meddic = saved  # 整体赋值，让 SQLAlchemy 识别 JSONB 变化
        db.flush()
        activity_service.record(
            db, user, "opportunity", opp.id, "meddic_updated",
            f"更新了赢单要素：{'、'.join(changed)}", subject=opp,
        )  # fmt: skip
    return to_out(opp)


# ---------- 评估 ----------


def _materials(db: Session, opp: Opportunity) -> tuple[list[Followup], list[Contact]]:
    followups = list(
        db.scalars(
            select(Followup)
            .where(Followup.customer_id == opp.customer_id)
            .order_by(func.coalesce(Followup.occurred_at, Followup.created_at).desc())
            .limit(20)
        )
    )
    contacts = list(db.scalars(select(Contact).where(Contact.customer_id == opp.customer_id)))
    return followups, contacts


_KEYWORDS: dict[str, tuple[str, ...]] = {
    "identify_pain": ("痛点", "问题", "困难", "麻烦", "效率低", "人工", "担心", "顾虑", "瓶颈"),
    "metrics": ("节省", "提升", "降低", "%", "万", "小时", "人力", "效率", "成本"),
    "decision_criteria": ("选型", "标准", "要求", "对比", "国产", "私有化", "性能", "竞品"),
    "decision_process": ("招标", "流程", "立项", "审批", "采购", "评审", "上会", "预算"),
}


def rule_assess(followups: list[Followup], contacts: list[Contact]) -> AssessOut:
    """没有模型时的初步判断：关键词命中 → 待验证（需要销售确认），联系人角色 → 决策人 / 支持者。"""
    text = "\n".join(f.content for f in followups)
    items: list[Suggestion] = []
    for key, words in _KEYWORDS.items():
        hits = [w for w in words if w in text]
        if hits:
            line = next((ln for ln in text.splitlines() if any(w in ln for w in hits)), "")
            items.append(Suggestion(key=key, status="partial", evidence=line[:200] or None))  # type: ignore[arg-type]
    eb = [c for c in contacts if c.role == "decision_maker"]
    if eb:
        names = "、".join(c.name for c in eb)
        items.append(
            Suggestion(
                key="economic_buyer", status="partial", evidence=f"联系人里标注的决策人：{names}"
            )
        )
    champ = [c for c in contacts if c.role == "influencer"]
    if champ:
        names = "、".join(c.name for c in champ)
        items.append(
            Suggestion(
                key="champion", status="partial", evidence=f"可能的支持者（影响者）：{names}"
            )
        )
    found = {i.key for i in items}
    missing = [ITEMS[k][0] for k in ORDER if k not in found]
    summary = (
        f"跟进记录里还看不到：{'、'.join(missing)}" if missing else "各项都有线索，需要逐项确认"
    )
    return AssessOut(source="rule", summary=summary, items=items)


ASSESS_PROMPT = """你是 ToB 销售教练，按 MEDDIC 评估一个商机的赢单要素。
只根据给出的跟进记录和联系人判断，不要编造；没有证据的项标 missing。
- confirmed：客户明确说过 / 已经见到，证据确凿
- partial：有线索但还没确认
- missing：完全没有信息
evidence 用一句话引用或概括依据（missing 时可为空）。summary 一句话指出最大的缺口和下一步。
六项：identify_pain 痛点、metrics 量化收益、economic_buyer 经济决策人、decision_criteria 决策标准、
decision_process 决策流程、champion 内部支持者。"""


def _context_text(opp: Opportunity, followups: list[Followup], contacts: list[Contact]) -> str:
    people = "\n".join(
        f"- {c.name}（{c.title or '职务未知'}，"
        f"{CONTACT_ROLE_LABELS.get(c.role or '', '角色未标注')}）"
        for c in contacts
    )
    notes = "\n".join(
        f"- [{(f.occurred_at or f.created_at):%Y-%m-%d}] {f.content}" for f in followups
    )
    stage = STAGE_LABELS.get(opp.stage, opp.stage)
    return (
        f"商机：{opp.name}，阶段：{stage}，金额：{opp.amount / 100:,.0f} 元\n"
        f"联系人：\n{people or '（无）'}\n跟进记录（最近 20 条）：\n{notes or '（无）'}"
    )


def assess(db: Session, user: CurrentUser, opportunity_id: uuid.UUID, llm: Any) -> AssessOut:
    """AI 评估（只读，不保存）。llm 为 None 或调用失败时按规则判断。"""
    opp = opp_service.get_opportunity(db, user, opportunity_id)
    followups, contacts = _materials(db, opp)
    if llm is not None and followups:
        try:
            judge = llm.with_structured_output(MeddicAssessment, method="function_calling")
            out = judge.invoke(
                [
                    SystemMessage(ASSESS_PROMPT),
                    HumanMessage(_context_text(opp, followups, contacts)),
                ]
            )
            if isinstance(out, MeddicAssessment):
                return AssessOut(source="ai", summary=out.summary, items=out.items)
        except Exception:
            logger.warning("meddic assess: llm failed, fallback to rules", exc_info=True)
    return rule_assess(followups, contacts)
