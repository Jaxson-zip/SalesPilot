"""催办审批：报价 / 报销在等主管审批时，负责人可以提醒一下本团队主管（站内通知，30 分钟一次）。"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.crm.models import Approval, Expense, Notification, Quote
from app.crm.services import notification_service

REMIND_EVERY = timedelta(minutes=30)
RULE_TOO_SOON = "approval_remind_too_soon"
RULE_NOT_PENDING = "approval_not_pending"
KIND = {"quote": "报价单", "expense": "报销单"}


class RemindIn(BaseModel):
    target_type: Literal["quote", "expense"]
    target_id: uuid.UUID


class RemindOut(BaseModel):
    notified: int  # 收到提醒的主管人数


def remind(db: Session, user: CurrentUser, body: RemindIn) -> RemindOut:
    model = Quote if body.target_type == "quote" else Expense
    target = db.get(model, body.target_id)
    ensure_owner(target, user)
    assert target is not None
    approval = db.scalar(
        select(Approval).where(
            Approval.target_type == body.target_type,
            Approval.target_id == target.id,
            Approval.status == "pending",
        )
    )
    if approval is None:
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "这张单子不在待审批状态，不需要催办",
            {"rule": RULE_NOT_PENDING},
        )
    link = f"/approvals?id={approval.id}"
    last = db.scalar(
        select(Notification.created_at)
        .where(Notification.type == "approval_remind", Notification.link == link)
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    now = datetime.now(UTC)
    if last is not None and now - last < REMIND_EVERY:
        wait = int((REMIND_EVERY - (now - last)).total_seconds() // 60) + 1
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"已经催过了，{wait} 分钟后可以再催",
            {"rule": RULE_TOO_SOON, "wait_minutes": wait},
        )
    kind = KIND[body.target_type]
    managers = notification_service.team_managers(db, target.team_id)
    n = notification_service.notify(
        db,
        managers,
        "approval_remind",
        f"{user.name} 催办：{kind} {target.code} 等你审批",
        approval.reason,
        link,
    )
    return RemindOut(notified=n)
