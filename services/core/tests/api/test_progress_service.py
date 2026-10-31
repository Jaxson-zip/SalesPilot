"""记一次进展：跟进 + 下一步 + 推进阶段在一个事务里写入，任何一步失败都不留半截数据。"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import Role
from app.common.db import get_sessionmaker
from app.common.errors import BizError
from app.crm.models import Followup, Opportunity, Task
from app.crm.services.demo import DEMO_USERS
from app.crm.services.progress_service import NextStepIn, ProgressIn, record_progress
from seed.data import C_MINGLI, C_YUEHAI, demo_id

SALES = DEMO_USERS[Role.SALES]


@pytest.fixture
def db() -> Iterator[Session]:
    """用完回滚：不在测试库里留数据。"""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _step() -> NextStepIn:
    return NextStepIn(
        title="发合同草稿", due_at=datetime.now(UTC) + timedelta(days=3), type="email"
    )


def test_followup_task_and_stage_together(db: Session) -> None:
    opp_id = demo_id("opp:mingli")
    data = ProgressIn(
        customer_id=C_MINGLI,
        opportunity_id=opp_id,
        type="visit",
        content="王律师同意进入商务谈判",
        next_step=_step(),
        stage="negotiation",
    )
    out = record_progress(db, SALES, data, "agent")
    assert out.followup.content == "王律师同意进入商务谈判"
    assert out.task is not None and out.task.subject_type == "opportunity"
    assert out.task.subject_id == opp_id
    assert out.opportunity is not None and out.opportunity.stage == "negotiation"
    assert db.get(Opportunity, opp_id).stage == "negotiation"  # type: ignore[union-attr]


def test_followup_only_on_customer(db: Session) -> None:
    out = record_progress(
        db, SALES, ProgressIn(customer_id=C_MINGLI, content="电话沟通", next_step=_step())
    )
    assert out.opportunity is None
    assert out.task is not None and out.task.subject_type == "customer"


def test_stage_needs_opportunity(db: Session) -> None:
    data = ProgressIn(customer_id=C_MINGLI, content="想推进", stage="negotiation")
    with pytest.raises(BizError) as e:
        record_progress(db, SALES, data)
    assert e.value.code == 40001


def test_failed_stage_rolls_back_everything(db: Session) -> None:
    """已赢单的商机不能再改阶段：报错后同一事务里的跟进和任务都不提交。"""
    content = "回归：已赢单商机改阶段失败"
    data = ProgressIn(
        customer_id=C_YUEHAI,
        opportunity_id=demo_id("opp:yuehai"),
        content=content,
        next_step=_step(),
        stage="negotiation",
    )
    with pytest.raises(BizError) as e:
        record_progress(db, SALES, data)
    assert e.value.code == 42201
    db.rollback()
    assert db.scalar(select(Followup).where(Followup.content == content)) is None
    assert db.scalar(select(Task).where(Task.title == "发合同草稿")) is None
