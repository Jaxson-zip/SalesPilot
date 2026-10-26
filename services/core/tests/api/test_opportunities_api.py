"""商机 / 漏斗 / 工作台 / 动态接口（接口契约 §1、§2）。"""

import uuid

from fastapi.testclient import TestClient

from app.crm.services.demo import demo_id
from seed.data import C_MINGLI, C_PC3H, PL_IT
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker

OPP_PC3H = demo_id("opp:pc3h")  # 王磊的商机
OPP_MINGLI = demo_id("opp:mingli")


def new_opp(client: TestClient, tracker: Tracker, **extra: object) -> dict:
    body = {
        "customer_id": str(C_MINGLI),
        "name": f"测试商机-{uuid.uuid4().hex[:6]}",
        "amount": 1_000_000,
    }
    r = client.post("/api/opportunities", json={**body, **extra}, headers=SALES_H)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    tracker.opportunities.append(uuid.UUID(data["id"]))
    return data


def test_list_scope_sales_vs_manager(client: TestClient) -> None:
    mine = client.get("/api/opportunities?page_size=100", headers=SALES_H).json()["data"]
    names = {o["name"] for o in mine["items"]}
    assert "合同审查私有化" in names and "病历质控" not in names
    team = client.get("/api/opportunities?view=team&page_size=100", headers=MANAGER_H).json()
    assert "病历质控" in {o["name"] for o in team["data"]["items"]}
    # 销售传 view=all 按 mine 处理
    as_all = client.get("/api/opportunities?view=all&page_size=100", headers=SALES_H).json()
    assert as_all["data"]["total"] == mine["total"]


def test_list_fields_and_filters(client: TestClient) -> None:
    r = client.get("/api/opportunities?stage=proposal&q=明理", headers=SALES_H)
    items = r.json()["data"]["items"]
    assert [o["name"] for o in items] == ["合同审查私有化"]
    item = items[0]
    assert {"id", "name", "customer", "stage", "amount", "win_rate", "expected_close_date",
            "product_line", "owner", "updated_at"} <= set(item)  # fmt: skip
    assert item["customer"]["name"] == "深圳明理律师事务所"
    assert item["product_line"]["pack"] == "llm_deploy" and item["owner"]["name"] == "张晨"


def test_list_invalid_stage(client: TestClient) -> None:
    assert client.get("/api/opportunities?stage=bad", headers=SALES_H).json()["code"] == 40001


def test_detail_permission(client: TestClient) -> None:
    r = client.get(f"/api/opportunities/{OPP_PC3H}", headers=SALES_H)
    assert r.status_code == 404 and r.json()["code"] == 40401
    assert client.get(f"/api/opportunities/{OPP_PC3H}", headers=MANAGER_H).json()["code"] == 0
    assert client.get(f"/api/opportunities/{OPP_PC3H}", headers=SALES2_H).json()["code"] == 0
    detail = client.get(f"/api/opportunities/{OPP_MINGLI}", headers=SALES_H).json()["data"]
    assert isinstance(detail["quotes"], list) and isinstance(detail["activities"], list)


def test_create_defaults_and_validation(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    assert opp["stage"] == "lead" and opp["win_rate"] == 10 and opp["owner"]["name"] == "张晨"
    bad = client.post(
        "/api/opportunities",
        json={"customer_id": str(C_MINGLI), "name": "x", "amount": -1},
        headers=SALES_H,
    )
    assert bad.json()["code"] == 40001


def test_create_on_invisible_customer(client: TestClient) -> None:
    body = {"customer_id": str(C_PC3H), "name": "越权", "amount": 1}
    r = client.post("/api/opportunities", json=body, headers=SALES_H)
    assert r.status_code == 404 and r.json()["code"] == 40401


def test_create_with_unknown_product_line(client: TestClient) -> None:
    body = {
        "customer_id": str(C_MINGLI),
        "name": "x",
        "amount": 1,
        "product_line_id": str(uuid.uuid4()),
    }
    assert client.post("/api/opportunities", json=body, headers=SALES_H).json()["code"] == 40001


def test_patch_fields(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    body = {"amount": 2_500_000, "win_rate": 40, "expected_close_date": "2026-12-31",
            "product_line_id": str(PL_IT)}  # fmt: skip
    r = client.patch(f"/api/opportunities/{opp['id']}", json=body, headers=SALES_H)
    data = r.json()["data"]
    assert data["amount"] == 2_500_000 and data["win_rate"] == 40
    assert data["product_line"]["pack"] == "it_office"
    bad = client.patch(f"/api/opportunities/{opp['id']}", json={"win_rate": 101}, headers=SALES_H)
    assert bad.json()["code"] == 40001
    other = client.patch(f"/api/opportunities/{OPP_PC3H}", json={"amount": 1}, headers=SALES_H)
    assert other.json()["code"] == 40401


def test_stage_flow_and_final_state(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}/stage"
    assert (
        client.patch(url, json={"stage": "qualified"}, headers=SALES_H).json()["data"]["stage"]
        == "qualified"
    )
    # 主管看得到但不是负责人：40301 not_owner（接口契约 §0）
    by_manager = client.patch(url, json={"stage": "proposal"}, headers=MANAGER_H).json()
    assert by_manager["code"] == 40301 and by_manager["data"]["rule"] == "not_owner"
    assert client.patch(url, json={"stage": "proposal"}, headers=SALES_H).json()["code"] == 0
    detail = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    contents = [a["content"] for a in detail["activities"] if a["action"] == "stage_changed"]
    assert "线索 → 需求确认" in contents and "需求确认 → 方案报价" in contents

    no_reason = client.patch(url, json={"stage": "lost"}, headers=SALES_H)
    assert no_reason.json()["code"] == 40001
    lost = client.patch(url, json={"stage": "lost", "lost_reason": "预算取消"}, headers=SALES_H)
    assert lost.json()["data"]["lost_reason"] == "预算取消"
    final = client.patch(url, json={"stage": "proposal"}, headers=SALES_H)
    assert final.status_code == 422 and final.json()["code"] == 42201
    assert final.json()["data"]["rule"] == "opportunity_stage_final"


def test_stage_change_forbidden_for_other_sales(client: TestClient) -> None:
    r = client.patch(
        f"/api/opportunities/{OPP_PC3H}/stage", json={"stage": "proposal"}, headers=SALES_H
    )
    assert r.json()["code"] == 40401


def test_pipeline_summary(client: TestClient) -> None:
    data = client.get("/api/pipeline/summary", headers=SALES_H).json()["data"]
    assert [s["stage"] for s in data["stages"]] == [
        "lead",
        "qualified",
        "proposal",
        "negotiation",
        "won",
        "lost",
    ]
    assert 0 <= data["weighted_amount"] <= data["total_amount"]
    team = client.get("/api/pipeline/summary?view=team", headers=MANAGER_H).json()["data"]
    assert team["total_amount"] > data["total_amount"]  # 团队包含王磊的商机


def test_dashboard(client: TestClient) -> None:
    sales = client.get("/api/dashboard", headers=SALES_H).json()["data"]
    assert sales["won_amount_month"] >= 81_000_000 + 28_600_000  # 演示数据：粤海 + 南山本月赢单
    assert sales["open_opportunities"] >= 4 and sales["pending_approvals"] >= 2
    assert sales["estimated_commission_month"] >= sales["confirmed_commission_month"] > 0
    assert {f["stage"] for f in sales["funnel"]} >= {"lead", "qualified", "proposal", "won"}
    manager = client.get("/api/dashboard?view=team", headers=MANAGER_H).json()["data"]
    assert manager["pending_approvals"] >= 2 and manager["open_amount"] > sales["open_amount"]
    assert client.get("/api/dashboard?view=bad", headers=SALES_H).json()["code"] == 40001


def test_activities_scope(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    client.patch(
        f"/api/opportunities/{opp['id']}/stage", json={"stage": "qualified"}, headers=SALES_H
    )
    url = f"/api/activities?subject_type=opportunity&subject_id={opp['id']}"
    mine = client.get(url, headers=SALES_H).json()["data"]["items"]
    assert any(a["action"] == "stage_changed" and a["actor"]["name"] == "张晨" for a in mine)
    # 可见范围跟随商机负责人：主管能看到本团队销售的动态，同组其他销售看不到
    team = client.get(url, headers=MANAGER_H).json()["data"]["items"]
    assert any(a["action"] == "stage_changed" for a in team)
    assert client.get(url, headers=SALES2_H).json()["data"]["items"] == []
    assert len(client.get("/api/activities?limit=3", headers=ADMIN_H).json()["data"]["items"]) <= 3
    assert client.get("/api/activities?limit=0", headers=SALES_H).json()["code"] == 40001
