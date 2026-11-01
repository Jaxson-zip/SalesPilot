"""回款记录：登记带到账日期 / 流水号 / 备注，查看记录，冲正（负数记录 + 原因）。"""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.crm.services.codes import local_today
from app.crm.services.demo import demo_id
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker
from tests.api.test_quotes_contracts_api import _accepted_contract


def _pay(client: TestClient, cid: str, **body: object) -> dict:
    return client.post(f"/api/contracts/{cid}/payments", json=body, headers=MANAGER_H).json()


def test_payment_records_reconciliation_fields(client: TestClient, tracker: Tracker) -> None:
    cid = _accepted_contract(client, tracker)["id"]
    day = (local_today() - timedelta(days=2)).isoformat()
    r = _pay(client, cid, amount=6_000_000, received_on=day, reference_no=" BK-001 ", note="首付款")
    assert r["code"] == 0 and r["data"]["paid_amount"] == 6_000_000
    _pay(client, cid, amount=1_000_000)  # 不传日期按今天
    rows = client.get(f"/api/contracts/{cid}/payments", headers=SALES_H).json()["data"]
    assert [p["amount"] for p in rows] == [1_000_000, 6_000_000]  # 新的在前
    first = rows[1]
    assert first["received_on"] == day and first["reference_no"] == "BK-001"
    assert first["note"] == "首付款" and first["created_by"]["name"]
    assert rows[0]["received_on"] == local_today().isoformat()


def test_payment_input_errors(client: TestClient, tracker: Tracker) -> None:
    cid = _accepted_contract(client, tracker)["id"]
    future = (local_today() + timedelta(days=1)).isoformat()
    assert _pay(client, cid, amount=1, received_on=future)["code"] == 40001
    assert _pay(client, cid, amount=1, reference_no="x" * 65)["code"] == 40001
    other = client.get(f"/api/contracts/{cid}/payments", headers=SALES2_H)
    assert other.json()["code"] == 40401  # 看不到合同就看不到回款记录


def test_reverse_payment(client: TestClient, tracker: Tracker) -> None:
    """登记错了：冲正后已回款减回去、状态回到执行中、提成按新比例重算，原记录保留。"""
    cid = _accepted_contract(client, tracker)["id"]
    total = client.get(f"/api/contracts/{cid}", headers=SALES_H).json()["data"]["amount"]
    _pay(client, cid, amount=total, reference_no="BK-WRONG")
    pid = client.get(f"/api/contracts/{cid}/payments", headers=SALES_H).json()["data"][0]["id"]
    url = f"/api/contracts/{cid}/payments/{pid}/reverse"

    assert client.post(url, json={"reason": "录错"}, headers=SALES_H).json()["code"] == 40301
    assert client.post(url, json={"reason": "录错"}, headers=ADMIN_H).json()["code"] == 40301
    assert client.post(url, json={"reason": ""}, headers=MANAGER_H).json()["code"] == 40001

    done = client.post(url, json={"reason": "金额录错"}, headers=MANAGER_H).json()["data"]
    assert done["paid_amount"] == 0 and done["status"] == "active"
    assert done["commission"]["confirmed"] == 0
    rows = client.get(f"/api/contracts/{cid}/payments", headers=SALES_H).json()["data"]
    rev = next(p for p in rows if p["reversal_of"] == pid)
    assert rev["amount"] == -total and rev["reason"] == "金额录错"
    assert next(p for p in rows if p["id"] == pid)["reversed_by"] == rev["id"]
    acts = client.get(f"/api/activities?subject_type=contract&subject_id={cid}", headers=SALES_H)
    assert "payment_reverse" in {a["action"] for a in acts.json()["data"]["items"]}

    again = client.post(url, json={"reason": "再冲一次"}, headers=MANAGER_H).json()
    assert again["code"] == 42201 and again["data"]["rule"] == "payment_already_reversed"
    rev_url = f"/api/contracts/{cid}/payments/{rev['id']}/reverse"
    assert client.post(rev_url, json={"reason": "冲正"}, headers=MANAGER_H).json()["code"] == 40001
    missing = f"/api/contracts/{cid}/payments/{uuid.uuid4()}/reverse"
    assert client.post(missing, json={"reason": "录错"}, headers=MANAGER_H).json()["code"] == 40401


def test_seeded_paid_contract_has_payment_record(client: TestClient) -> None:
    cid = demo_id("contract:yuehai")
    rows = client.get(f"/api/contracts/{cid}/payments", headers=SALES_H).json()["data"]
    contract = client.get(f"/api/contracts/{cid}", headers=SALES_H).json()["data"]
    assert sum(p["amount"] for p in rows) == contract["paid_amount"] > 0
