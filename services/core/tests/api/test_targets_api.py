"""业绩目标：主管设置本团队目标、各角色看到的范围、完成额与预测口径、月份校验、工作台目标。"""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Contract, Opportunity, SalesTarget, User
from app.crm.services import target_service
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES
from app.rules.crm_calc import LOCAL_TZ
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
# 用一个远期月份，不受演示数据里本月合同的影响
MONTH = datetime.now(UTC).astimezone(LOCAL_TZ).date().replace(day=1)
FUTURE = date(MONTH.year + (MONTH.month + 5) // 12, (MONTH.month + 5) % 12 + 1, 1)
KEY = f"{FUTURE:%Y-%m}"


@pytest.fixture(autouse=True)
def clean_targets() -> Iterator[None]:
    yield
    with session_scope() as db:
        db.execute(delete(SalesTarget).where(SalesTarget.month == FUTURE))


def _put(client: TestClient, items: list[dict[str, object]], h: dict[str, str] = MANAGER_H):
    return client.put(f"/api/targets/{KEY}", json={"items": items}, headers=h)


def test_manager_sets_team_targets_and_sees_totals(client: TestClient) -> None:
    r = _put(
        client,
        [
            {"user_id": str(SALES.id), "amount": 50_000_000},
            {"user_id": str(EXTRA_SALES.id), "amount": 30_000_000},
        ],
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["month"] == KEY
    assert data["editable"] is True
    assert data["time_progress"] == 0  # 未来的月份
    rows = {row["user"]["name"]: row for row in data["rows"]}
    assert {SALES.name, EXTRA_SALES.name, MANAGER.name} <= set(rows)
    assert rows[SALES.name]["target"] == 50_000_000
    assert rows[MANAGER.name]["target"] is None
    assert data["total"]["target"] == 80_000_000
    # 改一个、清一个
    data = _put(
        client,
        [
            {"user_id": str(SALES.id), "amount": 60_000_000},
            {"user_id": str(EXTRA_SALES.id), "amount": None},
        ],
    ).json()["data"]
    rows = {row["user"]["name"]: row for row in data["rows"]}
    assert rows[SALES.name]["target"] == 60_000_000
    assert rows[EXTRA_SALES.name]["target"] is None
    assert data["total"]["target"] == 60_000_000


def test_scope_by_role(client: TestClient) -> None:
    _put(client, [{"user_id": str(EXTRA_SALES.id), "amount": 10_000_000}])
    mine = client.get(f"/api/targets?month={KEY}", headers=SALES_H).json()["data"]
    assert [r["user"]["name"] for r in mine["rows"]] == [SALES.name]
    assert mine["editable"] is False
    assert mine["total"]["target"] is None  # 看不到同事的目标
    other = client.get(f"/api/targets?month={KEY}", headers=SALES2_H).json()["data"]
    assert other["total"]["target"] == 10_000_000
    admin = client.get(f"/api/targets?month={KEY}", headers=ADMIN_H).json()["data"]
    assert admin["editable"] is False
    assert any(r["team_name"] for r in admin["rows"])
    assert all(r["role"] in {"sales", "manager"} for r in admin["rows"])


def test_only_manager_of_the_team_can_set(client: TestClient) -> None:
    item = [{"user_id": str(SALES.id), "amount": 1}]
    assert _put(client, item, SALES_H).status_code == 403
    assert _put(client, item, ADMIN_H).status_code == 403
    with session_scope() as db:
        outsider = db.scalar(
            select(User.id).where(User.team_id != MANAGER.team_id, User.role == "sales")
        )
    if outsider:
        r = _put(client, [{"user_id": str(outsider), "amount": 1}])
        assert r.status_code == 400
        assert "本团队" in r.json()["message"]
    assert _put(client, [{"user_id": str(SALES.id), "amount": -1}]).status_code == 400


def test_month_validation(client: TestClient) -> None:
    for bad in ("2026-13", "202610", "2020-01"):
        r = client.get(f"/api/targets?month={bad}", headers=SALES_H)
        assert r.status_code == 400, bad
    assert client.get("/api/targets", headers=SALES_H).json()["data"]["month"] == f"{MONTH:%Y-%m}"


def test_achieved_and_forecast_follow_contracts_and_pipeline() -> None:
    """完成额按合同签订月份和负责人；预测是预计当月成交的进行中商机 金额 × 赢率。"""
    start = datetime.combine(FUTURE, datetime.min.time(), LOCAL_TZ)
    with session_scope() as db:
        customer_id = db.scalar(select(Contract.customer_id).limit(1))
        c = Contract(
            code="HT-TGT-TEST",
            customer_id=customer_id,
            amount=12_000_000,
            owner_id=SALES.id,
            team_id=SALES.team_id,
            created_at=start.replace(day=3),
        )
        o = Opportunity(
            customer_id=customer_id,
            name="目标预测测试",
            stage="proposal",
            amount=10_000_000,
            win_rate=40,
            expected_close_date=FUTURE.replace(day=20),
            owner_id=SALES.id,
            team_id=SALES.team_id,
        )
        db.add_all([c, o])
        db.add(
            SalesTarget(owner_id=SALES.id, team_id=SALES.team_id, month=FUTURE, amount=24_000_000)
        )
        db.flush()
        try:
            b = target_service.board(db, SALES, KEY)
            row = b.rows[0]
            assert (row.achieved, row.contracts, row.forecast) == (12_000_000, 1, 4_000_000)
            assert row.rate == 0.5
            assert b.total.rate == 0.5
        finally:
            db.rollback()


def test_dashboard_shows_month_target(client: TestClient) -> None:
    with session_scope() as db:
        db.execute(delete(SalesTarget).where(SalesTarget.month == MONTH))
    assert client.get("/api/dashboard", headers=SALES_H).json()["data"]["target_month"] is None
    try:
        with session_scope() as db:
            db.add(SalesTarget(owner_id=SALES.id, team_id=SALES.team_id, month=MONTH, amount=500))
            db.add(
                SalesTarget(owner_id=EXTRA_SALES.id, team_id=SALES.team_id, month=MONTH, amount=300)
            )
        assert client.get("/api/dashboard", headers=SALES_H).json()["data"]["target_month"] == 500
        team = client.get("/api/dashboard", headers=MANAGER_H).json()["data"]
        assert team["target_month"] == 800
    finally:
        with session_scope() as db:
            db.execute(delete(SalesTarget).where(SalesTarget.month == MONTH))
