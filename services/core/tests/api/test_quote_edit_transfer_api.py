"""报价调价、转移负责人、同事列表（接口契约 v3 §11、§14、§16）。"""

import uuid

from fastapi.testclient import TestClient

from app.crm.services.demo import EXTRA_SALES, demo_id
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker, make_tier
from tests.api.test_opportunities_api import new_opp
from tests.api.test_quotes_contracts_api import GOOD, LOW, act, create_quote
from tests.api.test_tasks_api import new_task

ADMIN_ID = demo_id("user:admin")


def patch_items(
    client: TestClient, qid: str, body: dict, headers: dict[str, str] = SALES_H
) -> dict:
    return client.patch(f"/api/quotes/{qid}/items", json=body, headers=headers).json()


# ---------- §11 同事列表 ----------


def test_users_team_and_admin(client: TestClient) -> None:
    team = client.get("/api/users?scope=team", headers=SALES_H).json()["data"]
    assert {u["name"] for u in team["items"]} == {"张晨", "李薇", "王磊"}
    first = team["items"][0]
    assert first == {"id": first["id"], "name": "李薇", "role": "manager", "active": True}
    # 销售传 scope=all 仍然只看本团队
    as_all = client.get("/api/users?scope=all", headers=SALES_H).json()["data"]
    assert as_all["total"] == 3
    admin = client.get("/api/users?scope=all", headers=ADMIN_H).json()["data"]
    assert "周敏" in {u["name"] for u in admin["items"]} and admin["total"] == 4
    assert client.get("/api/users?scope=bad", headers=SALES_H).json()["code"] == 40001


# ---------- §14 报价调价 ----------


def test_patch_items_recomputes_by_rules(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD))  # 原价 15 万，成本 9 万，毛利 40%
    before = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert before["discount_rate"] == 0 and before["list_price"] == 15_000_000
    assert before["valid_until"]
    body = {
        "items": [{"sku": "T-0", "qty": 2}, {"sku": "SW-MONITOR", "qty": 1}],
        "discount_rate": 0.05,
    }
    data = patch_items(client, qid, body)["data"]
    assert [i["sku"] for i in data["items"]] == ["T-0", "SW-MONITOR"]  # T-1 被移除，新增目录物料
    assert data["items"][0]["unit_price"] == 10_000_000  # 原明细单价保留
    assert data["list_price"] == 20_000_000 + data["items"][1]["unit_price"]
    assert data["total_price"] == round(data["list_price"] * 0.95)
    assert data["total_cost"] == 14_000_000 + data["items"][1]["unit_cost"]
    expected = round((data["total_price"] - data["total_cost"]) / data["total_price"], 4)
    assert data["margin_rate"] == expected and data["discount_rate"] == 0.05


def test_discount_over_limit_goes_to_approval(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD))
    body = {"items": [{"sku": "T-0", "qty": 1}, {"sku": "T-1", "qty": 1}], "discount_rate": 0.15}
    data = patch_items(client, qid, body)["data"]
    assert data["margin_rate"] == 0.2941  # 毛利仍高于 25%
    submitted = act(client, qid, "submit")["data"]
    assert submitted["status"] == "pending_approval"
    reason = submitted["approvals"][0]["reason"]
    assert "折扣 15.0%" in reason and "毛利" not in reason
    locked = patch_items(client, qid, body)
    assert locked["code"] == 42201 and locked["data"]["rule"] == "quote_not_editable"


def test_low_margin_after_edit_goes_to_approval(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD))
    body = {"items": [{"sku": "T-0", "qty": 3}], "discount_rate": 0.1}  # 硬件毛利 30% → 折后 22%
    data = patch_items(client, qid, body)["data"]
    assert data["margin_rate"] == 0.2222
    reason = act(client, qid, "submit")["data"]["approvals"][0]["reason"]
    assert "毛利 22.2% < 25%" in reason and "折扣" not in reason


def test_patch_items_errors(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(LOW))
    ok_body = {"items": [{"sku": "T-0", "qty": 1}], "discount_rate": 0}
    manager = patch_items(client, qid, ok_body, MANAGER_H)
    assert manager["code"] == 40301 and manager["data"]["rule"] == "not_owner"
    admin = patch_items(client, qid, ok_body, ADMIN_H)
    assert admin["code"] == 40301 and admin["data"]["rule"] == "role_forbidden"
    assert patch_items(client, qid, ok_body, SALES2_H)["code"] == 40401
    unknown = patch_items(client, qid, {"items": [{"sku": "NOPE", "qty": 1}]})
    assert unknown["code"] == 40001 and unknown["data"]["errors"][0]["sku"] == "NOPE"
    dup = {"items": [{"sku": "T-0", "qty": 1}, {"sku": "T-0", "qty": 2}]}
    assert patch_items(client, qid, dup)["code"] == 40001
    assert patch_items(client, qid, {**ok_body, "discount_rate": 1})["code"] == 40001
    assert patch_items(client, qid, {"items": []})["code"] == 40001
    assert patch_items(client, qid, {"items": [{"sku": "T-0", "qty": 0}]})["code"] == 40001


def test_patch_items_extra_charges(client: TestClient, tracker: Tracker) -> None:
    """目录以外的费用：自己填名称、单价、成本，计入总价和毛利；再次保存可以改；名称单价必填。"""
    qid = create_quote(tracker, make_tier(GOOD))  # 原价 15 万，成本 9 万
    rush = {"sku": "extra-rush", "qty": 1, "name": "加急实施费", "unit_price": 1_000_000}
    trip = {
        "sku": "extra-trip",
        "qty": 2,
        "name": "现场差旅",
        "unit": "次",
        "unit_price": 300_000,
        "unit_cost": 250_000,
    }
    body = {"items": [{"sku": "T-0", "qty": 1}, {"sku": "T-1", "qty": 1}, rush, trip]}
    data = patch_items(client, qid, body)["data"]
    assert data["total_price"] == 15_000_000 + 1_000_000 + 600_000
    assert data["total_cost"] == 9_000_000 + 500_000
    extra = {i["sku"]: i for i in data["items"]}
    assert extra["extra-rush"]["unit"] == "项" and extra["extra-rush"]["category"] == "service"
    assert (
        extra["extra-trip"]["name"] == "现场差旅"
        and extra["extra-trip"]["subtotal_cost"] == 500_000
    )

    # 再保存时改单价、删掉差旅
    again = patch_items(
        client, qid, {"items": [{**rush, "unit_price": 800_000}, {"sku": "T-0", "qty": 1}]}
    )
    assert again["data"]["total_price"] == 10_000_000 + 800_000

    missing = patch_items(client, qid, {"items": [{"sku": "extra-x", "qty": 1, "name": "无单价"}]})
    assert missing["code"] == 40001 and missing["data"]["errors"][0]["sku"] == "extra-x"


# ---------- §16 转移负责人 ----------


def _setup_customer(client: TestClient, tracker: Tracker) -> tuple[dict, dict, str]:
    body = {"name": f"测试转移客户-{uuid.uuid4().hex[:6]}"}
    customer = client.post("/api/customers", json=body, headers=SALES_H).json()["data"]
    tracker.customers.append(uuid.UUID(customer["id"]))
    opp = new_opp(client, tracker, customer_id=customer["id"])
    new_task(client, tracker, opp["id"])
    qid = create_quote(tracker, make_tier(GOOD), opp["id"])
    return customer, opp, qid


def test_transfer_customer_with_open_business(client: TestClient, tracker: Tracker) -> None:
    customer, opp, qid = _setup_customer(client, tracker)
    body = {"customer_ids": [customer["id"], customer["id"]], "to_user_id": str(EXTRA_SALES.id)}
    r = client.post("/api/customers/transfer", json=body, headers=MANAGER_H).json()
    assert r["code"] == 0
    assert r["data"] == {"transferred": 1, "opportunities": 1, "tasks": 1, "quotes": 1}
    # 新负责人看得到，原负责人看不到
    for path in (f"customers/{customer['id']}", f"opportunities/{opp['id']}", f"quotes/{qid}"):
        assert client.get(f"/api/{path}", headers=SALES2_H).json()["code"] == 0, path
        assert client.get(f"/api/{path}", headers=SALES_H).json()["code"] == 40401, path
    tasks = client.get(f"/api/tasks?subject_id={opp['id']}", headers=SALES2_H).json()["data"]
    assert tasks["total"] == 1 and tasks["items"][0]["owner"]["name"] == "王磊"
    acts = client.get(f"/api/activities?subject_id={customer['id']}", headers=SALES2_H).json()
    assert any(
        a["action"] == "transfer" and "张晨 → 王磊" in a["content"] for a in acts["data"]["items"]
    )
    notes = client.get("/api/notifications?unread=true&limit=100", headers=SALES2_H).json()
    assert any(
        n["type"] == "customer_assigned"
        and customer["name"] in n["title"]
        and n["link"] == f"/customers/{customer['id']}"
        for n in notes["data"]["items"]
    )
    # 再转一次给同一个人：不重复计数
    again = client.post("/api/customers/transfer", json=body, headers=MANAGER_H).json()
    assert again["data"]["transferred"] == 0


def test_transfer_errors(client: TestClient, tracker: Tracker) -> None:
    customer, _, _ = _setup_customer(client, tracker)
    body = {"customer_ids": [customer["id"]], "to_user_id": str(EXTRA_SALES.id)}
    url = "/api/customers/transfer"
    for headers in (SALES_H, ADMIN_H):
        r = client.post(url, json=body, headers=headers).json()
        assert r["code"] == 40301 and r["data"]["rule"] == "role_forbidden"
    to_admin = client.post(url, json={**body, "to_user_id": str(ADMIN_ID)}, headers=MANAGER_H)
    assert to_admin.json()["code"] == 40301 and to_admin.json()["data"]["rule"] == "not_team"
    missing_user = {**body, "to_user_id": str(uuid.uuid4())}
    assert client.post(url, json=missing_user, headers=MANAGER_H).json()["code"] == 40401
    missing = {**body, "customer_ids": [str(uuid.uuid4())]}
    assert client.post(url, json=missing, headers=MANAGER_H).json()["code"] == 40401
    empty = {**body, "customer_ids": []}
    assert client.post(url, json=empty, headers=MANAGER_H).json()["code"] == 40001
    # 失败的请求不会转移任何东西
    assert client.get(f"/api/customers/{customer['id']}", headers=SALES_H).json()["code"] == 0
