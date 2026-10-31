"""「下一步建议」规则：按这单的状态出建议，警示排前面，终态商机只看回款。"""

import uuid
from datetime import UTC, datetime

from app.crm.schemas.common import CustomerBrief
from app.crm.schemas.opportunity import OpportunityItem
from app.crm.schemas.task import NextTask
from app.crm.services.deal_state_service import DealContract, DealFollowup, DealQuote, DealState
from app.crm.services.suggestion_service import suggest

NOW = datetime(2026, 10, 31, tzinfo=UTC)


def _opp(**extra: object) -> OpportunityItem:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "合同审查私有化",
        "customer": CustomerBrief(id=uuid.uuid4(), name="明理律所"),
        "stage": "proposal",
        "amount": 50_000_000,
        "win_rate": 50,
        "expected_close_date": None,
        "product_line": None,
        "owner": None,
        "updated_at": NOW,
    }
    return OpportunityItem.model_validate({**base, **extra})


def _task(overdue: bool) -> NextTask:
    return NextTask(id=uuid.uuid4(), title="电话确认预算", due_at=NOW, overdue=overdue)


def _state(opp: OpportunityItem, **extra: object) -> DealState:
    return DealState.model_validate(
        {"opportunity": opp, "last_followup": None, "quote": None, "contract": None, **extra}
    )


def _quote(status: str) -> DealQuote:
    return DealQuote(
        id=uuid.uuid4(),
        code="Q-001",
        status=status,
        status_label=status,
        total_price=48_000_000,
        margin_rate=0.3,
        updated_at=NOW,
    )


def kinds(s: DealState) -> list[str]:
    return [x.kind for x in suggest(s)]


def test_healthy_deal_has_no_suggestions() -> None:
    s = _state(_opp(next_task=_task(False)), quote=_quote("sent"))
    assert kinds(s) == []


def test_stale_without_next_step_and_quote() -> None:
    opp = _opp(stale=True, idle_days=21, meddic_risks=["经济决策人"], competitors=["某云"])
    followup = DealFollowup(at=NOW, type_label="电话", content="客户说下月再看")
    out = suggest(_state(opp, last_followup=followup))
    assert [x.kind for x in out] == [
        "stale",
        "no_next_step",
        "meddic_gap",
        "no_quote",
        "competitor",
    ]
    assert out[0].level == "warn" and "21 天" in out[0].title
    assert out[0].detail == "客户说下月再看"
    assert all(x.opportunity_id == opp.id for x in out)
    assert "合同审查私有化" in out[3].prompt


def test_overdue_task_and_unsent_quote() -> None:
    s = _state(_opp(next_task=_task(True)), quote=_quote("approved"))
    assert kinds(s) == ["quote_unsent", "task_overdue"]


def test_lead_without_quote_is_fine() -> None:
    assert "no_quote" not in kinds(_state(_opp(stage="lead", next_task=_task(False))))


def test_won_deal_only_checks_payment() -> None:
    contract = DealContract(
        id=uuid.uuid4(),
        code="HT-001",
        amount=100,
        paid_amount=0,
        overdue_amount=100,
        overdue_days=9,
    )
    won = _opp(stage="won", stale=True, idle_days=40)
    assert kinds(_state(won, contract=contract)) == ["overdue_payment"]
    assert kinds(_state(won)) == []
