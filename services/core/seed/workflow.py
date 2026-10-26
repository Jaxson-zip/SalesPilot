"""v3 演示数据：任务（下一步行动）、停滞商机、通知。到期时间相对当前时间计算，任何时候导入都成立。

覆盖的演示场景：
- 今天到期：明理「合同审查私有化」给王律师发修订版方案
- 已逾期：华南智能制造「质检助手」电话跟进刘经理（2 天前到期）
- 没有下一步：星河设计「IT 设备换新」、前海云帆「AI 客服」没有未完成任务
- 停滞：星河设计「IT 设备换新」最近一次跟进在 20 天前（≥ rules.yaml pipeline.stale_days）
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.crm.models import Expense, Followup, Notification, Opportunity, Quote, Task
from app.crm.services.demo import demo_id
from app.rules.crm_calc import LOCAL_TZ
from seed.business_data import E_MINGLI, Q_HNZZ
from seed.data import C_HNZZ, C_MINGLI, C_NANSHAN, C_PC3H, C_XINGHE, MANAGER, SALES

OPP_MINGLI = demo_id("opp:mingli")
OPP_HNZZ = demo_id("opp:hnzz")
OPP_XINGHE = demo_id("opp:xinghe")
OPP_PC3H = demo_id("opp:pc3h")
STALE_DAYS_AGO = 20


def _at(days: int, hour: int) -> datetime:
    """北京时间：今天 + days 天的 hour 点。"""
    today = datetime.now(UTC).astimezone(LOCAL_TZ).date()
    return datetime.combine(today + timedelta(days=days), datetime.min.time(), LOCAL_TZ).replace(
        hour=hour
    )


def _tasks() -> list[dict[str, Any]]:
    opp, cust = "opportunity", "customer"
    return [
        {"key": "mingli:today", "title": "给王律师发送修订版方案", "type": "email",
         "due_at": _at(0, 23), "subject_type": opp, "subject_id": OPP_MINGLI,
         "customer_id": C_MINGLI, "owner": SALES, "note": "补充审计日志与数据不出内网的说明"},
        {"key": "hnzz:overdue", "title": "电话跟进刘经理确认报价", "type": "call",
         "due_at": _at(-2, 10), "subject_type": opp, "subject_id": OPP_HNZZ,
         "customer_id": C_HNZZ, "owner": SALES, "note": None},
        {"key": "nanshan:week", "title": "回访校本知识库使用情况", "type": "visit",
         "due_at": _at(3, 15), "subject_type": cust, "subject_id": C_NANSHAN,
         "customer_id": C_NANSHAN, "owner": SALES, "note": None},
        {"key": "pc3h:tomorrow", "title": "预约信息科做病历质控演示", "type": "meeting",
         "due_at": _at(1, 10), "subject_type": opp, "subject_id": OPP_PC3H,
         "customer_id": C_PC3H, "owner": None, "note": None},
        {"key": "mingli:done", "title": "确认 50 人并发与合同审查场景", "type": "call",
         "due_at": _at(-3, 10), "subject_type": opp, "subject_id": OPP_MINGLI,
         "customer_id": C_MINGLI, "owner": SALES, "note": None, "done_at": _at(-3, 16)},
    ]  # fmt: skip


def seed_tasks(db: Session) -> None:
    for row in _tasks():
        opp_owner = db.get(Opportunity, row["subject_id"])
        owner_id = row["owner"].id if row["owner"] else (opp_owner.owner_id if opp_owner else None)
        team_id = SALES.team_id
        values = {k: v for k, v in row.items() if k not in ("key", "owner", "done_at")}
        done_at = row.get("done_at")
        db.merge(
            Task(
                id=demo_id(f"task:{row['key']}"),
                **values,
                done=done_at is not None,
                done_at=done_at,
                owner_id=owner_id,
                team_id=team_id,
            )
        )


def seed_stale(db: Session) -> None:
    """星河设计的商机：创建于 30 天前，最近一次跟进在 20 天前，此后没有任何动态。"""
    long_ago = datetime.now(UTC) - timedelta(days=STALE_DAYS_AGO)
    opp = db.get(Opportunity, OPP_XINGHE)
    if opp is not None:
        opp.created_at = datetime.now(UTC) - timedelta(days=30)
    db.merge(
        Followup(
            id=demo_id("fu:xinghe:1"),
            customer_id=C_XINGHE,
            type="visit",
            source="manual",
            content="上门了解 40 台办公电脑换新需求，周总说等年底预算批下来再谈。",
            occurred_at=long_ago,
            created_at=long_ago,
            owner_id=SALES.id,
            team_id=SALES.team_id,
        )
    )


def seed_notifications(db: Session) -> None:
    """主管的两条待审批通知（对应种子里的两条待审批记录）。"""
    quote, expense = db.get(Quote, Q_HNZZ), db.get(Expense, E_MINGLI)
    rows = [
        ("pending:quote", f"待审批：报价单 {quote.code if quote else ''}", "毛利低于底线"),
        ("pending:expense", f"待审批：报销单 {expense.code if expense else ''}", "人均超出标准"),
    ]
    for key, title, body in rows:
        db.merge(
            Notification(
                id=demo_id(f"notification:{key}"),
                user_id=MANAGER.id,
                type="approval_pending",
                title=title,
                body=body,
                link="/approvals",
                read=False,
                read_at=None,
                dedupe_key=None,
            )
        )


def seed_workflow(db: Session) -> None:
    seed_tasks(db)
    seed_stale(db)
    seed_notifications(db)
