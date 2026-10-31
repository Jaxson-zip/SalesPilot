"""商机 / 客户的下一步建议接口：规则计算，带交给 AI 的话；看不到的数据 40401。"""

import uuid

from fastapi.testclient import TestClient

from seed.data import C_MINGLI, C_PC3H, demo_id
from tests.api.conftest import MANAGER_H, SALES_H

OPP_MINGLI = demo_id("opp:mingli")


def test_opportunity_suggestions(client: TestClient) -> None:
    r = client.get(f"/api/opportunities/{OPP_MINGLI}/suggestions", headers=SALES_H)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert isinstance(rows, list)
    for row in rows:
        assert row["opportunity_id"] == str(OPP_MINGLI)
        assert row["prompt"] and row["level"] in ("warn", "info")


def test_opportunity_suggestions_not_visible(client: TestClient) -> None:
    other = client.get(f"/api/opportunities/{demo_id('opp:pc3h')}/suggestions", headers=SALES_H)
    assert other.json()["code"] == 40401  # 王磊的商机，张晨看不到
    missing = client.get(f"/api/opportunities/{uuid.uuid4()}/suggestions", headers=SALES_H)
    assert missing.json()["code"] == 40401


def test_customer_suggestions(client: TestClient) -> None:
    r = client.get(f"/api/customers/{C_MINGLI}/suggestions", headers=MANAGER_H)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    levels = [row["level"] for row in rows]
    assert levels == sorted(levels, key=lambda lv: lv != "warn")  # 警示在前


def test_customer_suggestions_not_visible(client: TestClient) -> None:
    r = client.get(f"/api/customers/{C_PC3H}/suggestions", headers=SALES_H)
    assert r.json()["code"] == 40401
