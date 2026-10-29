"""成交链路的衔接：出报价推进到「方案报价」、发送报价后自动建跟进任务、回款到期前提醒、
软件外包按里程碑拆回款计划。"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import Role
from app.common.db import get_sessionmaker, session_scope
from app.crm.models import Contract, Customer, Notification, Opportunity, PaymentPlan, Quote, Task
from app.crm.services import jobs, quote_service
from app.crm.services.demo import DEMO_USERS
from app.packs.registry import get_configurator
from app.packs.software_outsourcing.requirement import SoftwareRequirement
from app.rules.crm_calc import LOCAL_TZ
from tests.api.conftest import SALES_H, Tracker
from tests.api.test_opportunities_api import new_opp

SALES = DEMO_USERS[Role.SALES]
REQ = SoftwareRequirement.model_validate(
    {"platforms": ["web"], "modules": [{"key": "content", "name": "资讯发布"}]}
)


def _tier():
    return {t.tier: t for t in get_configurator("software_outsourcing").configure(REQ)}["standard"]


def _quote(tracker: Tracker, opp_id: str | None, stage: str | None = None) -> Quote:
    with session_scope() as db:
        if stage and opp_id:
            db.get(Opportunity, uuid.UUID(opp_id)).stage = stage  # type: ignore[union-attr]
        out = quote_service.create_from_tier(
            db,
            SALES,
            pack="software_outsourcing",
            tier=_tier(),
            opportunity_id=uuid.UUID(opp_id) if opp_id else None,
            idempotency_key=f"test-flow-{uuid.uuid4().hex}",
        )
        tracker.quotes.append(out.id)
        return db.get(Quote, out.id)  # type: ignore[return-value]


def _stage(opp_id: str) -> str:
    with session_scope() as db:
        return db.get(Opportunity, uuid.UUID(opp_id)).stage  # type: ignore[union-attr]


def test_quote_moves_early_opportunity_to_proposal(client: TestClient, tracker: Tracker) -> None:
    lead = new_opp(client, tracker)
    _quote(tracker, lead["id"], stage="qualified")
    assert _stage(lead["id"]) == "proposal"
    # 谈判中的不往回退
    talking = new_opp(client, tracker)
    _quote(tracker, talking["id"], stage="negotiation")
    assert _stage(talking["id"]) == "negotiation"


def test_send_quote_schedules_followup_task(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    quote = _quote(tracker, opp["id"])
    with session_scope() as db:
        db.get(Quote, quote.id).status = "approved"  # type: ignore[union-attr]
    r = client.post(f"/api/quotes/{quote.id}/send", headers=SALES_H)
    assert r.status_code == 200, r.text
    with session_scope() as db:
        tasks = list(db.scalars(select(Task).where(Task.subject_id == uuid.UUID(opp["id"]))))
        assert len(tasks) == 1
        task = tasks[0]
        assert task.title.startswith(f"跟进报价 {quote.code}") and task.type == "call"
        due = task.due_at.astimezone(LOCAL_TZ)
        today = datetime.now(UTC).astimezone(LOCAL_TZ).date()
        assert (due.date() - today).days == 3 and due.hour == 10


@pytest.fixture
def db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_payment_due_job_reminds_owner_once(db: Session) -> None:
    now = datetime.now(UTC)
    owner = {"owner_id": SALES.id, "team_id": SALES.team_id}
    c = Customer(name=f"回款提醒测试-{uuid.uuid4().hex[:6]}", level="C", **owner)
    db.add(c)
    db.flush()
    contract = Contract(
        code=f"HT-DUE-{uuid.uuid4().hex[:6]}",
        customer_id=c.id,
        amount=100_000,
        paid_amount=0,
        status="active",
        **owner,
    )
    db.add(contract)
    db.flush()
    today = now.astimezone(LOCAL_TZ).date()
    soon = PaymentPlan(
        contract_id=contract.id,
        seq=1,
        name="首付款",
        amount=30_000,
        due_date=today + timedelta(2),
        **owner,
    )
    far = PaymentPlan(
        contract_id=contract.id,
        seq=2,
        name="尾款",
        amount=70_000,
        due_date=today + timedelta(30),
        **owner,
    )
    db.add_all([soon, far])
    db.flush()
    jobs.JOBS["payment_due"].run(db, now, {})
    jobs.JOBS["payment_due"].run(db, now, {})  # 再跑一次不重复
    notes = list(
        db.scalars(select(Notification).where(Notification.dedupe_key.like("payment_due:%")))
    )
    mine = [n for n in notes if n.dedupe_key in (f"payment_due:{soon.id}", f"payment_due:{far.id}")]
    assert len(mine) == 1 and mine[0].user_id == SALES.id
    assert "2 天后" in (mine[0].body or "") and "¥300.00" in (mine[0].body or "")


def test_software_contract_uses_milestone_plan(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    quote = _quote(tracker, opp["id"])
    with session_scope() as db:
        db.get(Quote, quote.id).status = "sent"  # type: ignore[union-attr]
    assert client.post(f"/api/quotes/{quote.id}/accept", headers=SALES_H).status_code == 200
    with session_scope() as db:
        contract = db.scalar(select(Contract).where(Contract.quote_id == quote.id))
        assert contract is not None
        plans = db.scalars(
            select(PaymentPlan)
            .where(PaymentPlan.contract_id == contract.id)
            .order_by(PaymentPlan.seq)
        )
        assert [p.name for p in plans] == [
            "签约首付款",
            "原型与 UI 确认款",
            "上线验收款",
            "质保尾款",
        ]
