"""销售日报：从当天的真实操作（操作日志、跟进、任务）汇总事实，AI 写成草稿，本人改完提交。

事实只来自系统记录，AI 只负责组织语言，不编造数字；没有模型时按模板拼草稿。
主管 / 管理员看团队当天的提交情况，并可生成近 7 天的团队汇总。
"""

import datetime as dt
import logging
import uuid
from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.crm.models import AuditLog, Customer, DailyReport, Followup, Task, User
from app.crm.schemas.report import (
    DailyFacts,
    DailyReportIn,
    DailyReportOut,
    DailyStats,
    DraftOut,
    SummaryOut,
    TeamDailyOut,
    TeamMemberReport,
)
from app.crm.services import audit_service, notification_service, wecom_service
from app.crm.services.codes import LOCAL_TZ, local_today
from app.crm.services.wecom_service import PushIn, PushOut

logger = logging.getLogger(__name__)

# 不算「工作内容」的操作（登录、看电话、导出属于安全审计）
SKIP_ACTIONS = ("auth.", "contact.phone_view", "export.", "report.")
MAX_ITEMS = 40


def _range(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=LOCAL_TZ)
    return start, start + timedelta(days=1)


def _check_date(d: date) -> None:
    today = local_today()
    if d > today or d < today - timedelta(days=31):
        raise BizError(ErrorCode.VALIDATION, "只能查看或填写最近 31 天的日报")


def collect_facts(db: Session, user_id: uuid.UUID, d: date) -> DailyFacts:
    """当天的事实：操作日志（网页 + AI）、跟进内容、完成的任务、明天到期的任务。"""
    start, end = _range(d)
    logs = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.user_id == user_id,
                AuditLog.ok.is_(True),
                AuditLog.created_at >= start,
                AuditLog.created_at < end,
            )
            .order_by(AuditLog.created_at)
        )
    )
    logs = [lg for lg in logs if not lg.action.startswith(SKIP_ACTIONS)]
    names = audit_service.target_names(db, [lg.target_id for lg in logs])
    counts = Counter(lg.action for lg in logs)
    # 同一条文字只列一次；没有对象名的（如新建类操作）在后面标次数
    seen: Counter[str] = Counter()
    for lg in logs:
        target = names.get(str(lg.target_id)) if lg.target_id else None
        text = f"{lg.label}「{target}」" if target else lg.label
        if lg.source == "agent":
            text += "（AI）"
        seen[text] += 1
    actions = [t if n == 1 or "「" in t else f"{t} ×{n}" for t, n in seen.items()]

    rows = db.execute(
        select(Customer.name, Followup.content)
        .join(Customer, Customer.id == Followup.customer_id)
        .where(
            Followup.owner_id == user_id, Followup.created_at >= start, Followup.created_at < end
        )
        .order_by(Followup.created_at)
    ).all()
    followups = [f"{name}：{content[:120]}" for name, content in rows]

    done = list(
        db.scalars(
            select(Task.title).where(
                Task.owner_id == user_id, Task.done_at >= start, Task.done_at < end
            )
        )
    )
    t_start, t_end = _range(d + timedelta(days=1))
    tomorrow = list(
        db.scalars(
            select(Task.title)
            .where(
                Task.owner_id == user_id,
                Task.done.is_(False),
                Task.due_at >= t_start,
                Task.due_at < t_end,
            )
            .order_by(Task.due_at)
        )
    )
    stats = DailyStats(
        followups=len(followups),
        quotes=sum(v for k, v in counts.items() if k in ("quote.create", "quote.submit")),
        stage_changes=counts.get("opportunity.stage", 0),
        tasks_done=len(done),
        ai_actions=sum(1 for lg in logs if lg.source == "agent"),
    )
    return DailyFacts(
        stats=stats,
        actions=actions[:MAX_ITEMS],
        followups=followups[:MAX_ITEMS],
        tasks_done=done[:MAX_ITEMS],
        tomorrow=tomorrow[:MAX_ITEMS],
    )


def _get(db: Session, user_id: uuid.UUID, d: date) -> DailyReport | None:
    return db.scalar(
        select(DailyReport).where(DailyReport.user_id == user_id, DailyReport.report_date == d)
    )


def _require_writer(user: CurrentUser) -> None:
    if user.role == Role.ADMIN:
        raise BizError(ErrorCode.FORBIDDEN, "管理员不需要填写日报")


def get_daily(db: Session, user: CurrentUser, d: date) -> DailyReportOut:
    _require_writer(user)
    _check_date(d)
    r = _get(db, user.id, d)
    return DailyReportOut(
        date=d,
        status=r.status if r else "none",  # type: ignore[arg-type]
        content=r.content if r else "",
        submitted_at=r.submitted_at if r else None,
        facts=collect_facts(db, user.id, d),
    )


def save_daily(db: Session, user: CurrentUser, body: DailyReportIn) -> DailyReportOut:
    """保存草稿或提交（提交后仍可修改，再次提交会更新提交时间）。"""
    _require_writer(user)
    _check_date(body.date)
    r = _get(db, user.id, body.date)
    if r is None:
        r = DailyReport(user_id=user.id, team_id=user.team_id, report_date=body.date)
        db.add(r)
    r.content = body.content.strip()
    facts = collect_facts(db, user.id, body.date)
    r.stats = facts.stats.model_dump()
    if body.submit:
        r.status = "submitted"
        r.submitted_at = datetime.now(LOCAL_TZ)
        notification_service.resolve_keys(db, [f"report_remind:{user.id}:{body.date.isoformat()}"])
    db.flush()
    return DailyReportOut(
        date=body.date,
        status=r.status,  # type: ignore[arg-type]
        content=r.content,
        submitted_at=r.submitted_at,
        facts=facts,
    )


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {s}" for s in items)


def template_draft(facts: DailyFacts) -> str:
    s = facts.stats
    parts = [
        f"【今日概况】跟进 {s.followups} 次，报价 {s.quotes} 次，"
        f"推进商机阶段 {s.stage_changes} 次，完成任务 {s.tasks_done} 项。"
    ]
    if facts.followups:
        parts.append("【客户跟进】\n" + _bullets(facts.followups))
    others = [a for a in facts.actions if not a.startswith("记录跟进")]
    if others:
        parts.append("【其他工作】\n" + _bullets(others))
    if facts.tomorrow:
        parts.append("【明日计划】\n" + _bullets(facts.tomorrow))
    else:
        parts.append("【明日计划】\n- ")
    parts.append("【需要支持】\n- 无")
    return "\n\n".join(parts)


DRAFT_PROMPT = """你是销售助理，根据下面系统记录的当天工作事实，帮销售写一份简洁的工作日报草稿。
要求：
- 分为【今日概况】【客户跟进】【明日计划】【需要支持】四段，每段用「- 」列点；
- 只使用给出的事实，数字照抄，不要编造客户、金额或进展；没有的内容写「无」；
- 客户跟进按客户归纳，写清进展和下一步；明日计划优先列明天到期的任务，再根据跟进内容补充；
- 「需要支持」只在事实里出现预算、审批、价格、竞品等阻碍时提出，否则写「无」；
- 总字数 300 字以内，直接输出日报正文。"""


def _facts_text(facts: DailyFacts) -> str:
    s = facts.stats
    return (
        f"数字：跟进 {s.followups} 次，报价 {s.quotes} 次，阶段推进 {s.stage_changes} 次，"
        f"完成任务 {s.tasks_done} 项\n"
        f"系统操作：\n{_bullets(facts.actions) or '（无）'}\n"
        f"跟进内容：\n{_bullets(facts.followups) or '（无）'}\n"
        f"今天完成的任务：\n{_bullets(facts.tasks_done) or '（无）'}\n"
        f"明天到期的任务：\n{_bullets(facts.tomorrow) or '（无）'}"
    )


def _llm_text(llm: Any, system: str, human: str) -> str | None:
    try:
        out = llm.invoke([SystemMessage(system), HumanMessage(human)])
        text = str(getattr(out, "content", "") or "").strip()
        return text or None
    except Exception:
        logger.warning("report: llm failed, fallback to template", exc_info=True)
        return None


def draft_daily(db: Session, user: CurrentUser, d: date, llm: Any) -> DraftOut:
    """生成草稿（不保存）。当天没有任何记录时直接给模板，不调用模型。"""
    _require_writer(user)
    _check_date(d)
    facts = collect_facts(db, user.id, d)
    empty = not (facts.actions or facts.followups or facts.tasks_done)
    if llm is not None and not empty:
        text = _llm_text(llm, DRAFT_PROMPT, _facts_text(facts))
        if text:
            return DraftOut(source="ai", content=text)
    return DraftOut(source="template", content=template_draft(facts))


def _team_users(db: Session, user: CurrentUser) -> list[User]:
    if user.role == Role.SALES:
        raise BizError(ErrorCode.FORBIDDEN, "团队日报仅主管和管理员可以查看")
    # 只统计销售：主管自己的日报可写可不写，不出现在「未提交」名单里
    stmt = select(User).where(User.role == Role.SALES.value, User.active.is_(True))
    stmt = stmt.order_by(User.name)
    if user.role == Role.MANAGER:
        stmt = stmt.where(User.team_id == user.team_id)
    return list(db.scalars(stmt))


def team_daily(db: Session, user: CurrentUser, d: date) -> TeamDailyOut:
    """主管看本团队、管理员看全公司当天的日报提交情况；未提交的不显示内容。"""
    _check_date(d)
    users = _team_users(db, user)
    reports = {
        r.user_id: r
        for r in db.scalars(
            select(DailyReport).where(
                DailyReport.report_date == d, DailyReport.user_id.in_([u.id for u in users])
            )
        )
    }
    members = []
    for u in users:
        r = reports.get(u.id)
        submitted = r is not None and r.status == "submitted"
        stats = (
            DailyStats.model_validate(r.stats)
            if submitted and r and r.stats
            else collect_facts(db, u.id, d).stats
        )
        members.append(
            TeamMemberReport(
                user_id=u.id,
                name=u.name,
                status=r.status if r else "none",  # type: ignore[arg-type]
                content=r.content if submitted and r else None,
                submitted_at=r.submitted_at if r else None,
                stats=stats,
            )
        )
    members.sort(key=lambda m: (m.status != "submitted", m.name))
    return TeamDailyOut(
        date=d,
        submitted=sum(1 for m in members if m.status == "submitted"),
        total=len(members),
        members=members,
    )


SUMMARY_PROMPT = """你是销售主管的助理。根据团队成员近几天提交的日报和系统统计，写一份团队周汇总。
要求：
- 分为【整体情况】【重点进展】【风险与阻碍】【需要主管协调】四段，每段用「- 」列点；
- 只使用给出的内容，不编造客户和数字；提到具体事项时带上成员姓名；
- 没提交日报的成员在【整体情况】里点名；
- 400 字以内，直接输出正文。"""


def team_summary(db: Session, user: CurrentUser, days: int, llm: Any) -> SummaryOut:
    users = _team_users(db, user)
    d_to = local_today()
    d_from = d_to - timedelta(days=days - 1)
    reports = list(
        db.scalars(
            select(DailyReport)
            .where(
                DailyReport.user_id.in_([u.id for u in users]),
                DailyReport.status == "submitted",
                DailyReport.report_date >= d_from,
                DailyReport.report_date <= d_to,
            )
            .order_by(DailyReport.report_date)
        )
    )
    name = {u.id: u.name for u in users}
    totals: dict[uuid.UUID, Counter[str]] = {u.id: Counter() for u in users}
    for r in reports:
        totals[r.user_id].update({k: int(v) for k, v in (r.stats or {}).items()})
    lines = [
        f"- {name[uid]}：提交 {sum(1 for r in reports if r.user_id == uid)} 天，"
        f"跟进 {c['followups']} 次，报价 {c['quotes']} 次，阶段推进 {c['stage_changes']} 次"
        for uid, c in totals.items()
    ]
    missing = [name[uid] for uid in totals if not any(r.user_id == uid for r in reports)]
    header = f"【{d_from:%m-%d} 至 {d_to:%m-%d}】\n" + "\n".join(lines)
    if llm is not None and reports:
        body = "\n\n".join(
            f"{name[r.user_id]} {r.report_date:%m-%d}：\n{r.content[:800]}" for r in reports[-40:]
        )
        human = f"统计：\n{header}\n未提交：{'、'.join(missing) or '无'}\n\n日报原文：\n{body}"
        text = _llm_text(llm, SUMMARY_PROMPT, human)
        if text:
            return SummaryOut(source="ai", date_from=d_from, date_to=d_to, content=text)
    tail = f"\n\n未提交日报：{'、'.join(missing)}" if missing else ""
    return SummaryOut(
        source="template", date_from=d_from, date_to=d_to, content=f"【整体情况】\n{header}{tail}"
    )


def push_summary(db: Session, user: CurrentUser, body: PushIn) -> PushOut:
    _team_users(db, user)
    content = f"**团队日报汇总**（{user.name} 推送）\n\n{body.content}"
    return wecom_service.push_now(db, user, "report_summary", "团队日报汇总", content)


def remind_missing(db: Session, user: CurrentUser, d: dt.date) -> PushOut:
    """把当天还没提交日报的销售名单推到群里。"""
    team = team_daily(db, user, d)
    missing = [m.name for m in team.members if m.status != "submitted"]
    if not missing:
        raise BizError(ErrorCode.VALIDATION, "今天的日报都已提交，不需要提醒")
    names = "、".join(missing)
    content = (
        f'**日报提醒（{d:%m-%d}）**\n> 还没提交：<font color="warning">{names}</font>\n\n'
        f"请下班前到 {wecom_service.link('/reports', 'SalesPilot 日报')} 生成并提交。"
    )
    title = f"日报提醒：{len(missing)} 人"
    return wecom_service.push_now(db, user, "report_remind", title, content)
