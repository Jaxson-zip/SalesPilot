"""按人一键交接：主管把一名成员名下的客户、未完成任务、回款中的合同一次转给接手人。"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.common.db import session_scope
from app.crm.models import Activity, Contract, Customer, Notification, PaymentPlan, Task, User
from app.crm.services.codes import local_today
from app.crm.services.demo import EXTRA_SALES, TEAM_SOUTH_ID
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H

URL = "/api/customers/handover"


@pytest.fixture
def leaver() -> Iterator[dict[str, uuid.UUID]]:
    """临时建一名「离职」销售：1 个客户（含未完成任务）、回款中和已收齐的合同各 1 份。"""
    ids = {k: uuid.uuid4() for k in ("user", "customer", "task", "active", "paid")}
    owner = {"owner_id": ids["user"], "team_id": TEAM_SOUTH_ID}
    with session_scope() as db:
        db.add(User(id=ids["user"], name="交接测试", role="sales", team_id=TEAM_SOUTH_ID))
        db.flush()
        db.add(Customer(id=ids["customer"], name=f"交接测试客户-{ids['user'].hex[:6]}", **owner))
        db.flush()
        db.add(
            Task(
                id=ids["task"], title="回访", due_at=datetime.now(UTC) + timedelta(days=1),
                subject_type="customer", subject_id=ids["customer"],
                customer_id=ids["customer"], **owner,
            )
        )  # fmt: skip
        for key, status in (("active", "active"), ("paid", "paid")):
            db.add(
                Contract(
                    id=ids[key], code=f"T-{ids[key].hex[:8]}", customer_id=ids["customer"],
                    amount=100, paid_amount=100 if status == "paid" else 0, status=status, **owner,
                )
            )  # fmt: skip
        db.flush()
        db.add(
            PaymentPlan(
                contract_id=ids["active"], seq=1, name="全款", amount=100,
                due_date=local_today(), **owner,
            )
        )  # fmt: skip
    yield ids
    with session_scope() as db:
        contracts = [ids["active"], ids["paid"]]
        db.execute(delete(PaymentPlan).where(PaymentPlan.contract_id.in_(contracts)))
        db.execute(delete(Activity).where(Activity.subject_id.in_([*contracts, ids["customer"]])))
        db.execute(delete(Contract).where(Contract.id.in_(contracts)))
        db.execute(delete(Task).where(Task.id == ids["task"]))
        db.execute(delete(Customer).where(Customer.id == ids["customer"]))
        db.execute(
            delete(Notification).where(
                Notification.type == "customer_handover", Notification.title.contains("交接测试")
            )
        )
        db.execute(delete(User).where(User.id == ids["user"]))


def test_preview_then_handover_everything(client: TestClient, leaver: dict) -> None:
    src = str(leaver["user"])
    preview = client.get(f"{URL}/preview?from_user_id={src}", headers=MANAGER_H).json()
    assert preview["data"] == {
        "customers": 1, "opportunities": 0, "tasks": 1, "quotes": 0, "contracts": 1,
    }  # fmt: skip

    body = {"from_user_id": src, "to_user_id": str(EXTRA_SALES.id)}
    r = client.post(URL, json=body, headers=MANAGER_H).json()
    assert r["code"] == 0 and r["data"] == preview["data"]
    with session_scope() as db:
        assert db.get(Customer, leaver["customer"]).owner_id == EXTRA_SALES.id  # type: ignore[union-attr]
        assert db.get(Task, leaver["task"]).owner_id == EXTRA_SALES.id  # type: ignore[union-attr]
        assert db.get(Contract, leaver["active"]).owner_id == EXTRA_SALES.id  # type: ignore[union-attr]
        plan = db.scalars(select(PaymentPlan).where(PaymentPlan.contract_id == leaver["active"]))
        assert plan.one().owner_id == EXTRA_SALES.id
        # 已收齐的合同不交接
        assert db.get(Contract, leaver["paid"]).owner_id == leaver["user"]  # type: ignore[union-attr]
        note = db.scalars(
            select(Notification).where(
                Notification.user_id == EXTRA_SALES.id, Notification.type == "customer_handover"
            )
        ).first()
        assert note is not None and note.title == "交接测试 的客户交接给你"
    # 再交接一次：已经没有东西了
    again = client.post(URL, json=body, headers=MANAGER_H).json()["data"]
    assert again == {"customers": 0, "opportunities": 0, "tasks": 0, "quotes": 0, "contracts": 0}


def test_handover_errors(client: TestClient, leaver: dict) -> None:
    src = str(leaver["user"])
    body = {"from_user_id": src, "to_user_id": str(EXTRA_SALES.id)}
    for headers in (SALES_H, ADMIN_H):
        r = client.post(URL, json=body, headers=headers).json()
        assert r["code"] == 40301 and r["data"]["rule"] == "role_forbidden"
        p = client.get(f"{URL}/preview?from_user_id={src}", headers=headers).json()
        assert p["code"] == 40301
    same = client.post(URL, json={**body, "to_user_id": src}, headers=MANAGER_H).json()
    assert same["code"] == 42201 and same["data"]["rule"] == "handover_same_user"
    missing = client.post(URL, json={**body, "from_user_id": str(uuid.uuid4())}, headers=MANAGER_H)
    assert missing.json()["code"] == 40401
    users = client.get("/api/users?scope=all", headers=ADMIN_H).json()["data"]["items"]
    other = next(u["id"] for u in users if u["role"] == "admin")
    not_team = client.post(URL, json={**body, "from_user_id": other}, headers=MANAGER_H).json()
    assert not_team["code"] == 40301 and not_team["data"]["rule"] == "not_team"
    # 失败的请求不改数据
    with session_scope() as db:
        assert db.get(Customer, leaver["customer"]).owner_id == leaver["user"]  # type: ignore[union-attr]
