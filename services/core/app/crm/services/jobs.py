"""定时任务的具体内容：每个任务是 (db, now, options) → 一句运行结果。

都按「重复跑不会重复提醒」写：通知用 dedupe_key 去重，所以手动「立即运行」、重启后补跑都是安全的。
只有公海自动回收会改业务数据，默认关闭，由管理员开启。
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crm.models import Contract, Customer, DailyReport, Followup, Opportunity, Task, User
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import activity_service, notification_service, wecom_service
from app.crm.services.contract_service import due_soon_condition, overdue_condition, plan_states
from app.crm.services.opportunity_insights import last_activity
from app.crm.services.transfer_service import move_customer
from app.rules.crm_calc import day_bounds, idle_days_of, is_stale, local_date
from app.rules.loader import load_rules

JobFn = Callable[[Session, datetime, dict[str, Any]], str]

# 逾期任务只提醒最近一周内到期的（老数据不一次性刷屏）
OVERDUE_TASK_WINDOW = timedelta(days=7)
# 公海回收单次最多处理的客户数
RECYCLE_BATCH = 200


@dataclass(frozen=True)
class JobDef:
    name: str
    title: str
    description: str
    run_at: time
    enabled: bool
    weekdays_only: bool
    run: JobFn
    # 可在网页上改的参数及默认值（目前只有公海回收的天数）
    options: tuple[tuple[str, int], ...] = ()


def _task_due(db: Session, now: datetime, _: dict[str, Any]) -> str:
    start, end = day_bounds(now)
    day = local_date(now).isoformat()
    today = db.scalars(
        select(Task).where(Task.done.is_(False), Task.due_at >= start, Task.due_at < end)
    ).all()
    overdue = db.scalars(
        select(Task).where(
            Task.done.is_(False), Task.due_at < start, Task.due_at >= start - OVERDUE_TASK_WINDOW
        )
    ).all()
    sent = 0
    for t in today:
        sent += notification_service.notify_once(
            db,
            t.owner_id,
            "task_due",
            f"任务今天到期：{t.title}",
            f"task_due:{t.id}:{day}",  # 与查询通知时补生成的 key 相同，不会重复
            t.note,
            notification_service.task_link(t),
        )
    for t in overdue:
        sent += notification_service.notify_once(
            db,
            t.owner_id,
            "task_overdue",
            f"任务已逾期：{t.title}",
            f"task_overdue:{t.id}",
            f"原定 {local_date(t.due_at):%m-%d} 完成",
            notification_service.task_link(t),
        )
    return f"今天到期 {len(today)} 个、逾期 {len(overdue)} 个任务，新发提醒 {sent} 条"


def _payment_due(db: Session, now: datetime, _: dict[str, Any]) -> str:
    """到期前提醒负责人：可以提前开票、提醒客户走付款流程。每期只提醒一次。"""
    days = load_rules().payment.remind_days
    if days <= 0:
        return "到期前提醒已关闭（业务规则里设为 0 天）"
    contracts = list(
        db.scalars(select(Contract).where(Contract.status == "active", due_soon_condition(days)))
    )
    states = plan_states(db, contracts)
    names = dict(
        db.execute(
            select(Customer.id, Customer.name).where(
                Customer.id.in_({c.customer_id for c in contracts})
            )
        ).all()
    )
    today = local_date(now)
    periods = sent = 0
    for c in contracts:
        for plan, state in states[c.id]:
            left = (state.due_date - today).days
            if (
                state.status not in ("pending", "partial")
                or not 0 <= left <= days
                or not c.owner_id
            ):
                continue
            periods += 1
            when = "今天" if left == 0 else f"{left} 天后（{state.due_date:%m-%d}）"
            sent += notification_service.notify_once(
                db,
                c.owner_id,
                "payment_due",
                f"回款将到期：{c.code} {plan.name}",
                f"payment_due:{plan.id}",
                f"{names.get(c.customer_id, '')} 应收 ¥{(state.amount - state.paid) / 100:,.2f}，"
                f"{when}到期；需要发票的可以先申请开票",
                f"/contracts?plan={c.id}",
            )
    return f"{days} 天内到期 {periods} 期，新发提醒 {sent} 条"


def _payment_overdue(db: Session, now: datetime, _: dict[str, Any]) -> str:
    contracts = list(db.scalars(select(Contract).where(overdue_condition())))
    states = plan_states(db, contracts)
    names = dict(
        db.execute(
            select(Customer.id, Customer.name).where(
                Customer.id.in_({c.customer_id for c in contracts})
            )
        ).all()
    )
    periods = sent = 0
    lines: list[str] = []
    for c in contracts:
        receivers = {c.owner_id, *notification_service.team_managers(db, c.team_id)}
        for plan, state in states[c.id]:
            if state.status != "overdue":
                continue
            periods += 1
            owed = state.amount - state.paid
            title = f"回款逾期：{c.code} {plan.name}"
            customer = names.get(c.customer_id, "")
            body = f"{customer} 应收 ¥{owed / 100:,.2f}，已逾期 {state.overdue_days} 天"
            new = 0
            for uid in receivers:
                new += notification_service.notify_once(
                    db,
                    uid,
                    "payment_overdue",
                    title,
                    f"payment_overdue:{plan.id}:{uid}",
                    body,
                    f"/contracts?plan={c.id}",
                )
            if new:
                lines.append(f"> {c.code} {plan.name}：{body}")
            sent += new
    if lines:
        content = "**回款逾期提醒**\n" + "\n".join(lines[:20])
        content += f"\n\n请到 {wecom_service.link('/contracts', 'SalesPilot 合同')} 跟进。"
        wecom_service.queue(db, "payment_overdue", f"回款逾期 {len(lines)} 期", content)
    return f"逾期 {periods} 期（{len(contracts)} 份合同），新发提醒 {sent} 条"


def _stale_opportunities(db: Session, now: datetime, _: dict[str, Any]) -> str:
    opps = list(db.scalars(select(Opportunity).where(Opportunity.stage.not_in(FINAL_STAGES))))
    lasts = last_activity(db, opps)
    rules = load_rules()
    stale = sent = 0
    for o in opps:
        idle = idle_days_of(lasts[o.id], now)
        if not is_stale(o.stage, idle, rules) or o.owner_id is None:
            continue
        stale += 1
        # 每次「变成停滞」只提醒一次：有了新动态再停滞，会再提醒
        key = f"opp_stale:{o.id}:{local_date(lasts[o.id]).isoformat()}"
        sent += notification_service.notify_once(
            db,
            o.owner_id,
            "opportunity_stale",
            f"商机 {idle} 天没有进展：{o.name}",
            key,
            "写一条跟进或安排下一步，避免商机冷掉",
            f"/pipeline?opp={o.id}",
        )
    return f"停滞商机 {stale} 个，新发提醒 {sent} 条"


def _report_remind(db: Session, now: datetime, _: dict[str, Any]) -> str:
    d = local_date(now)
    sales = list(
        db.scalars(
            select(User).where(User.role == "sales", User.active.is_(True)).order_by(User.name)
        )
    )
    submitted = set(
        db.scalars(
            select(DailyReport.user_id).where(
                DailyReport.report_date == d, DailyReport.status == "submitted"
            )
        )
    )
    missing = [u for u in sales if u.id not in submitted]
    for u in missing:
        notification_service.notify_once(
            db,
            u.id,
            "report_remind",
            "今天的日报还没提交",
            f"report_remind:{u.id}:{d.isoformat()}",
            "AI 会根据今天的跟进和操作生成草稿，确认后提交即可",
            "/reports",
        )
    if missing:
        names = "、".join(u.name for u in missing)
        content = (
            f'**日报提醒（{d:%m-%d}）**\n> 还没提交：<font color="warning">{names}</font>\n\n'
            f"请下班前到 {wecom_service.link('/reports', 'SalesPilot 日报')} 生成并提交。"
        )
        wecom_service.queue(db, "report_remind_auto", f"日报提醒：{len(missing)} 人", content)
    return f"{len(sales)} 名销售中 {len(missing)} 人未提交，已提醒"


def _pool_recycle(db: Session, now: datetime, options: dict[str, Any]) -> str:
    days = int(options.get("days") or 90)
    cutoff = now - timedelta(days=days)
    last_fu = (
        select(Followup.customer_id, func.max(Followup.created_at).label("at"))
        .group_by(Followup.customer_id)
        .subquery()
    )
    open_opp = select(Opportunity.id).where(
        Opportunity.customer_id == Customer.id, Opportunity.stage.not_in(FINAL_STAGES)
    )
    stmt = (
        select(Customer)
        .outerjoin(last_fu, last_fu.c.customer_id == Customer.id)
        .where(
            Customer.owner_id.is_not(None),
            func.coalesce(last_fu.c.at, Customer.created_at) < cutoff,
            ~open_opp.exists(),
        )
        .order_by(Customer.created_at)
        .limit(RECYCLE_BATCH)
        .with_for_update(of=Customer, skip_locked=True)
    )
    customers = list(db.scalars(stmt))
    reason = f"超过 {days} 天没有跟进，系统自动退回公海"
    for c in customers:
        owner_id = c.owner_id
        assert owner_id is not None
        move_customer(db, c, {"owner_id": None, "team_id": c.team_id})
        activity_service.record_system(db, "customer", c.id, "pool_release", reason, c.team_id)
        notification_service.notify_once(
            db,
            owner_id,
            "customer_recycled",
            f"客户已退回公海：{c.name}",
            f"customer_recycled:{c.id}:{now.date().isoformat()}",
            reason,
            "/customers",
        )
    return f"退回公海 {len(customers)} 个客户（超过 {days} 天没有跟进、没有进行中的商机）"


JOBS: dict[str, JobDef] = {
    j.name: j
    for j in (
        JobDef(
            "task_due",
            "任务到期提醒",
            "给负责人发今天到期的任务；最近一周内逾期的任务各提醒一次。",
            time(8, 30),
            True,
            False,
            _task_due,
        ),
        JobDef(
            "payment_due",
            "回款到期提醒",
            "回款计划某一期快到期（默认提前 3 天，在业务规则里改）还没收齐：提醒合同负责人，"
            "可以提前开票、提醒客户付款；每期只提醒一次。",
            time(9, 0),
            True,
            False,
            _payment_due,
        ),
        JobDef(
            "payment_overdue",
            "回款逾期提醒",
            "回款计划某一期过了到期日还没收齐：提醒合同负责人和所在团队主管，每期只提醒一次；"
            "企业微信推送里勾选了「回款逾期」时同时推到群里。",
            time(9, 0),
            True,
            False,
            _payment_overdue,
        ),
        JobDef(
            "stale_opportunities",
            "商机停滞提醒",
            "进行中的商机超过业务规则里的停滞天数没有新动态：提醒负责人；有了新动态后再停滞会再提醒。",
            time(9, 0),
            True,
            False,
            _stale_opportunities,
        ),
        JobDef(
            "report_remind",
            "日报催交",
            "工作日下班前提醒还没提交日报的销售；企业微信推送里勾选了「自动催交日报」时同时推到群里。",
            time(18, 0),
            True,
            True,
            _report_remind,
        ),
        JobDef(
            "pool_recycle",
            "公海自动回收",
            "长期没有跟进、也没有进行中商机的客户自动退回公海，本团队其他销售可以领取。"
            "会改变客户负责人，默认关闭。",
            time(2, 0),
            False,
            False,
            _pool_recycle,
            (("days", 90),),
        ),
    )
}


def job_def(name: str) -> JobDef | None:
    return JOBS.get(name)


def new_run_key() -> str:
    return f"manual:{uuid.uuid4().hex[:12]}"
