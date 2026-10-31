"""「点进去就是那一条」需要的接口数据：动态带对象名称、报销按商机筛选。"""

from fastapi.testclient import TestClient

from seed.data import demo_id
from tests.api.conftest import SALES_H, Tracker
from tests.api.test_expenses_approvals_api import new_expense

OPP_MINGLI = demo_id("opp:mingli")


def test_activity_feed_names_each_subject(client: TestClient) -> None:
    rows = client.get("/api/activities", params={"limit": 50}, headers=SALES_H).json()["data"][
        "items"
    ]
    named = [r for r in rows if r["subject_type"] in ("customer", "opportunity", "quote")]
    assert named, "演示数据里应有客户 / 商机 / 报价的动态"
    assert all(r["subject_name"] for r in named)


def test_expenses_filtered_by_opportunity(client: TestClient, tracker: Tracker) -> None:
    linked = new_expense(client, tracker, opportunity_id=str(OPP_MINGLI))
    other = new_expense(client, tracker)
    params = {"opportunity_id": str(OPP_MINGLI), "page_size": 100}
    ids = [
        e["id"]
        for e in client.get("/api/expenses", params=params, headers=SALES_H).json()["data"]["items"]
    ]
    assert linked["id"] in ids and other["id"] not in ids


def test_expenses_filter_rejects_bad_opportunity_id(client: TestClient) -> None:
    r = client.get("/api/expenses", params={"opportunity_id": "not-a-uuid"}, headers=SALES_H)
    assert r.json()["code"] == 40001
