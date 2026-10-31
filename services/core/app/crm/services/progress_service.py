"""记一次进展：跟进 + 下一步 + 推进阶段，一个事务写入。

销售说「今天见了王律师，他们同意进商务谈判，周五前发合同草稿」时，这三件事是一回事：
分成三张确认卡既啰嗦，又可能出现「跟进记了、阶段没改」的半截数据。任何一步失败整体回滚。
赢单 / 输单不在这里：赢单要选报价生成合同、输单要写原因，仍走单独的阶段变更。
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.crm.schemas.opportunity import OpportunityItem, StageChange
from app.crm.schemas.task import TaskCreate, TaskItem, TaskType
from app.crm.services import followup_service, task_service
from app.crm.services import opportunity_service as opp_service
from app.crm.services.followup_service import FollowupCreate, FollowupOut

ActiveStage = Literal["lead", "qualified", "proposal", "negotiation"]


class NextStepIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime
    type: TaskType = "todo"


class ProgressIn(FollowupCreate):
    next_step: NextStepIn | None = None
    stage: ActiveStage | None = None


class ProgressOut(BaseModel):
    followup: FollowupOut
    task: TaskItem | None = None
    opportunity: OpportunityItem | None = None


def _task(data: ProgressIn, step: NextStepIn) -> TaskCreate:
    is_opp = data.opportunity_id is not None
    subject_id: uuid.UUID = data.opportunity_id or data.customer_id
    return TaskCreate(
        title=step.title,
        due_at=step.due_at,
        type=step.type,
        subject_type="opportunity" if is_opp else "customer",
        subject_id=subject_id,
    )


def record_progress(
    db: Session, user: CurrentUser, data: ProgressIn, source: str = "manual"
) -> ProgressOut:
    """调用方负责事务（session_scope / 请求级会话）：这里抛错时三件事都不会提交。"""
    if data.stage and data.opportunity_id is None:
        raise BizError(ErrorCode.VALIDATION, "推进阶段需要指定商机")
    followup = followup_service.add_followup(
        db,
        user,
        FollowupCreate(**data.model_dump(include=set(FollowupCreate.model_fields))),
        source,
    )
    task = (
        task_service.create_task(db, user, _task(data, data.next_step), source)
        if data.next_step
        else None
    )
    opportunity = None
    if data.stage and data.opportunity_id:
        opportunity = opp_service.change_stage(
            db, user, data.opportunity_id, StageChange(stage=data.stage), source
        )
    return ProgressOut(followup=followup, task=task, opportunity=opportunity)
