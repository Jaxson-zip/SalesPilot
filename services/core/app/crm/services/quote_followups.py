"""报价跟进任务：发送报价后建电话跟进任务，客户答复（接受 / 拒绝）后自动完成。"""

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError
from app.crm.models import Quote, Task
from app.crm.schemas.task import TaskCreate
from app.crm.services import task_service
from app.crm.services.codes import LOCAL_TZ, local_today
from app.rules.loader import RuleSet

FOLLOWUP_TITLE = "跟进报价 {code}：确认客户意见"


def close_followups(db: Session, quote: Quote, reason: str) -> None:
    """客户已答复：发送时建的跟进任务自动完成，不再按到期提醒。"""
    tasks = db.scalars(
        select(Task).where(
            Task.done.is_(False),
            Task.customer_id == quote.customer_id,
            Task.title == FOLLOWUP_TITLE.format(code=quote.code),
        )
    )
    for task in tasks:
        task.done, task.done_at = True, datetime.now(UTC)
        task.note = "\n".join(filter(None, [task.note, f"{reason}，自动完成"]))


def schedule_followup(db: Session, user: CurrentUser, quote: Quote, rules: RuleSet) -> str:
    """发送报价后建一条电话跟进任务（N 天后上午 10 点到期），返回追加到动态里的说明。"""
    days = rules.quote.followup_days
    subject_type, subject_id = (
        ("opportunity", quote.opportunity_id)
        if quote.opportunity_id
        else ("customer", quote.customer_id)
    )
    if days <= 0 or subject_id is None:
        return ""
    due = datetime.combine(local_today() + timedelta(days=days), time(10), tzinfo=LOCAL_TZ)
    data = TaskCreate(
        title=FOLLOWUP_TITLE.format(code=quote.code),
        due_at=due,
        subject_type=subject_type,  # type: ignore[arg-type]
        subject_id=subject_id,
        type="call",
    )
    try:
        task_service.create_task(db, user, data, "auto")
    except BizError:  # 商机 / 客户已转给别人：不替别人建任务
        return ""
    return f"，已建跟进任务（{due:%m-%d}）"
