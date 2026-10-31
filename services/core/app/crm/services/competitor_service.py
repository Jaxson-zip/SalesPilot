"""竞品战卡：管理员维护；所有人可查（现场拆招）；商机标注遇到的竞品；战绩按商机统计。

战绩（进行中 / 赢 / 输 + 最近的输单原因）把输单原因反馈回战卡，让打法越用越准。
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_configurer
from app.crm.models import Competitor, Opportunity
from app.crm.services import activity_service
from app.crm.services import opportunity_service as opp_service


class Objection(BaseModel):
    say: str = Field(min_length=1, max_length=300)
    respond: str = Field(min_length=1, max_length=1000)


class CompetitorIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    summary: str | None = Field(default=None, max_length=500)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    weaknesses: list[str] = Field(default_factory=list, max_length=20)
    win_tactics: list[str] = Field(default_factory=list, max_length=20)
    objections: list[Objection] = Field(default_factory=list, max_length=30)


class CompetitorStats(BaseModel):
    open: int = 0
    won: int = 0
    lost: int = 0
    lost_reasons: list[str] = Field(default_factory=list)  # 最近 3 条输单原因


class CompetitorOut(CompetitorIn):
    id: uuid.UUID
    updated_by: str | None = None
    stats: CompetitorStats = CompetitorStats()


class OppCompetitorsIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


def _require_admin(user: CurrentUser) -> None:
    ensure_configurer(user, "竞品战卡由系统管理员维护")


def _clean(items: list[str]) -> list[str]:
    return [s.strip() for s in items if s and s.strip()]


def _stats(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, CompetitorStats]:
    out = {i: CompetitorStats() for i in ids}
    if not ids:
        return out
    stmt = (
        select(Opportunity.competitor_ids, Opportunity.stage, Opportunity.lost_reason)
        .where(func.jsonb_array_length(Opportunity.competitor_ids) > 0)
        .order_by(Opportunity.updated_at.desc())
    )
    for comp_ids, stage, reason in db.execute(stmt):
        for raw in comp_ids or []:
            try:
                cid = uuid.UUID(str(raw))
            except ValueError:
                continue
            st = out.get(cid)
            if st is None:
                continue
            if stage == "won":
                st.won += 1
            elif stage == "lost":
                st.lost += 1
                if reason and len(st.lost_reasons) < 3:
                    st.lost_reasons.append(reason)
            else:
                st.open += 1
    return out


def to_out(c: Competitor, stats: CompetitorStats | None = None) -> CompetitorOut:
    return CompetitorOut(
        id=c.id,
        name=c.name,
        aliases=c.aliases or [],
        summary=c.summary,
        strengths=c.strengths or [],
        weaknesses=c.weaknesses or [],
        win_tactics=c.win_tactics or [],
        objections=[Objection.model_validate(o) for o in c.objections or []],
        updated_by=c.updated_by,
        stats=stats or CompetitorStats(),
    )


def _matches(c: Competitor, kw: str) -> bool:
    text = " ".join(
        [
            c.name,
            c.summary or "",
            *(c.aliases or []),
            *(c.weaknesses or []),
            *(c.win_tactics or []),
            *(f"{o.get('say', '')} {o.get('respond', '')}" for o in c.objections or []),
        ]
    ).lower()
    return all(part in text for part in kw.lower().split())


def list_competitors(db: Session, q: str | None = None) -> list[CompetitorOut]:
    """所有角色可查；q 匹配名称、别名、弱点、打法、常见说法（现场按客户原话搜）。"""
    rows = list(db.scalars(select(Competitor).where(Competitor.enabled).order_by(Competitor.name)))
    if q and q.strip():
        rows = [c for c in rows if _matches(c, q.strip())]
    stats = _stats(db, [c.id for c in rows])
    return [to_out(c, stats[c.id]) for c in rows]


def _apply(c: Competitor, data: CompetitorIn, user: CurrentUser) -> None:
    c.name = data.name.strip()
    c.aliases = _clean(data.aliases)
    c.summary = (data.summary or "").strip() or None
    c.strengths = _clean(data.strengths)
    c.weaknesses = _clean(data.weaknesses)
    c.win_tactics = _clean(data.win_tactics)
    c.objections = [o.model_dump() for o in data.objections]
    c.updated_by = user.name


def _check_name(db: Session, name: str, exclude: uuid.UUID | None = None) -> None:
    stmt = select(Competitor.id).where(func.lower(Competitor.name) == name.strip().lower())
    if exclude:
        stmt = stmt.where(Competitor.id != exclude)
    if db.scalar(stmt):
        raise BizError(ErrorCode.DUPLICATE, f"已有同名竞品：{name}")


def create_competitor(db: Session, user: CurrentUser, data: CompetitorIn) -> CompetitorOut:
    _require_admin(user)
    _check_name(db, data.name)
    c = Competitor(enabled=True)
    _apply(c, data, user)
    db.add(c)
    db.flush()
    return to_out(c)


def update_competitor(
    db: Session, user: CurrentUser, competitor_id: uuid.UUID, data: CompetitorIn
) -> CompetitorOut:
    _require_admin(user)
    c = db.get(Competitor, competitor_id)
    if c is None or not c.enabled:
        raise BizError(ErrorCode.NOT_FOUND)
    _check_name(db, data.name, competitor_id)
    _apply(c, data, user)
    db.flush()
    return to_out(c, _stats(db, [c.id])[c.id])


def delete_competitor(db: Session, user: CurrentUser, competitor_id: uuid.UUID) -> None:
    """软删除：商机上的历史标注和战绩统计不受影响。"""
    _require_admin(user)
    c = db.get(Competitor, competitor_id)
    if c is None or not c.enabled:
        raise BizError(ErrorCode.NOT_FOUND)
    c.enabled = False
    c.name = f"{c.name}（已删除 {uuid.uuid4().hex[:4]}）"[:100]  # 释放名称，允许重建同名竞品
    db.flush()


def opportunity_competitors(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID
) -> list[CompetitorOut]:
    opp = opp_service.get_opportunity(db, user, opportunity_id)
    ids = [uuid.UUID(str(i)) for i in opp.competitor_ids or []]
    if not ids:
        return []
    rows = {c.id: c for c in db.scalars(select(Competitor).where(Competitor.id.in_(ids)))}
    stats = _stats(db, list(rows))
    return [to_out(rows[i], stats[i]) for i in ids if i in rows and rows[i].enabled]


def set_opportunity_competitors(
    db: Session, user: CurrentUser, opportunity_id: uuid.UUID, body: OppCompetitorsIn
) -> list[CompetitorOut]:
    """负责人标注商机遇到的竞品（覆盖式），记一条商机动态。"""
    opp = opp_service.get_owned(db, user, opportunity_id)
    ids = list(dict.fromkeys(body.ids))
    found = list(db.scalars(select(Competitor).where(Competitor.id.in_(ids), Competitor.enabled)))
    if len(found) != len(ids):
        raise BizError(ErrorCode.NOT_FOUND, "竞品不存在或已删除")
    names = {c.id: c.name for c in found}
    opp.competitor_ids = [str(i) for i in ids]
    db.flush()
    text = "、".join(names[i] for i in ids) if ids else "（清空）"
    activity_service.record(
        db, user, "opportunity", opp.id, "competitors_updated", text, subject=opp
    )
    return opportunity_competitors(db, user, opportunity_id)


def find_for_chat(
    db: Session, user: CurrentUser, keyword: str | None, opportunity_id: uuid.UUID | None
) -> list[CompetitorOut]:
    """AI 工具用：按关键词（客户原话、竞品叫法）或商机查战卡。"""
    if opportunity_id:
        cards = opportunity_competitors(db, user, opportunity_id)
        if cards or not keyword:
            return cards
    if not keyword:
        return list_competitors(db)
    hits = list_competitors(db, keyword)
    if hits:
        return hits
    # 整句没有命中：按单个词再找一次（「客户说云上便宜」→ 云）
    rows = list(db.scalars(select(Competitor).where(Competitor.enabled)))
    words = [w for w in keyword.replace("，", " ").replace(",", " ").split() if len(w) >= 2]
    picked = [
        c
        for c in rows
        if any(a and a in keyword for a in [c.name, *(c.aliases or [])])
        or any(_matches(c, w) for w in words)
    ]
    stats = _stats(db, [c.id for c in picked])
    return [to_out(c, stats[c.id]) for c in picked]


def as_dict(c: CompetitorOut) -> dict[str, Any]:
    return c.model_dump(mode="json", exclude={"id", "updated_by"})
