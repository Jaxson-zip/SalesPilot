"""开票历史与并发：作废保留原票和原因；调整回款计划不会覆盖同时登记的发票。"""

import threading
import time
import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import PaymentPlan
from app.crm.schemas.finance import InvoiceIn, PaymentPlanLineIn, PaymentPlanUpdate
from app.crm.services import contract_service, invoice_service
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import MANAGER_H, SALES_H, Tracker
from tests.api.test_quotes_contracts_api import _accepted_contract


def _invoice(client: TestClient, cid: str, body: dict) -> dict:
    return client.post(
        f"/api/contracts/{cid}/payment-plan/1/invoice", json=body, headers=MANAGER_H
    ).json()


def test_void_keeps_original_invoice_and_reason(client: TestClient, tracker: Tracker) -> None:
    """回归：作废清空原发票号码、日期，原因只进通知；重新开票后查不到原票。"""
    cid = _accepted_contract(client, tracker)["id"]
    issue = {
        "action": "issue",
        "invoice_type": "special",
        "invoice_no": "No.111",
        "invoiced_on": "2026-10-08",
    }
    assert _invoice(client, cid, issue)["code"] == 0
    assert _invoice(client, cid, {"action": "void", "note": "  "})["code"] == 40001
    assert _invoice(client, cid, {"action": "void", "note": "抬头写错"})["code"] == 0
    plan = _invoice(client, cid, {**issue, "invoice_no": "No.222"})["data"]

    assert plan["items"][0]["invoice_no"] == "No.222"
    events = plan["invoice_events"]
    assert [e["action"] for e in events] == ["issue", "void", "issue"]
    void = events[1]
    assert void["invoice_no"] == "No.111" and void["invoiced_on"] == "2026-10-08"
    assert void["note"] == "抬头写错" and void["from_status"] == "issued"
    assert void["actor"]["name"] == DEMO_USERS[Role.MANAGER].name
    feed = client.get(f"/api/activities?subject_type=contract&subject_id={cid}", headers=SALES_H)
    contents = " ".join(a["content"] for a in feed.json()["data"]["items"])
    assert "No.111" in contents and "抬头写错" in contents


def test_invoice_activity_uses_specific_actions(client: TestClient, tracker: Tracker) -> None:
    """回归（复测 UX03）：申请、登记、作废、撤回都记成 invoice，工作台动态显示英文。"""
    cid = _accepted_contract(client, tracker)["id"]
    url = f"/api/contracts/{cid}/payment-plan/1/invoice"
    client.post(url, json={"action": "request"}, headers=SALES_H)
    _invoice(client, cid, {"action": "void", "note": "客户暂不需要"})
    _invoice(client, cid, {"action": "issue", "invoice_no": "No.333"})
    _invoice(client, cid, {"action": "void", "note": "金额有误"})
    feed = client.get(f"/api/activities?subject_type=contract&subject_id={cid}", headers=SALES_H)
    actions = [a["action"] for a in feed.json()["data"]["items"] if "invoice" in a["action"]]
    assert actions == ["invoice_void", "invoice_issue", "invoice_withdraw", "invoice_request"]


def test_plan_change_does_not_overwrite_concurrent_invoice(
    client: TestClient, tracker: Tracker
) -> None:
    """回归：调整计划先读各期（未开票）再删除重建；中间主管登记的发票被调整前的数据覆盖。"""
    cid = uuid.UUID(_accepted_contract(client, tracker)["id"])
    with session_scope() as db:
        plans = list(db.query(PaymentPlan).filter_by(contract_id=cid).order_by(PaymentPlan.seq))
        lines = [
            PaymentPlanLineIn(name=p.name, amount=p.amount, due_date=p.due_date) for p in plans
        ]
    lines[-1] = lines[-1].model_copy(update={"due_date": date(2099, 1, 1)})
    issued = threading.Event()
    errors: list[BaseException] = []

    def issue() -> None:
        try:
            with session_scope() as db:
                body = InvoiceIn(action="issue", invoice_no="No.999")
                invoice_service.act(db, DEMO_USERS[Role.MANAGER], cid, 1, body)
                issued.set()
                time.sleep(0.5)  # 登记了还没提交：调整计划这时开始
        except BaseException as exc:
            errors.append(exc)
            issued.set()

    def replan() -> None:
        try:
            issued.wait(5)
            with session_scope() as db:
                data = PaymentPlanUpdate(items=lines)
                contract_service.replace_payment_plan(db, DEMO_USERS[Role.SALES], cid, data)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=issue), threading.Thread(target=replan)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert not errors, errors
    with session_scope() as db:
        first = db.query(PaymentPlan).filter_by(contract_id=cid, seq=1).one()
        last = (
            db.query(PaymentPlan)
            .filter_by(contract_id=cid)
            .order_by(PaymentPlan.seq.desc())
            .first()
        )
        assert first.invoice_status == "issued" and first.invoice_no == "No.999"
        assert last is not None and last.due_date == date(2099, 1, 1)
