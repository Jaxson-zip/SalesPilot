"""报价状态机、成交生成合同和提成、回款确认提成（接口契约 §3、§4）。"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.common.auth import CurrentUser, Role
from app.common.db import session_scope
from app.crm.services import quote_service
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES, demo_id
from app.packs.base import SolutionTier
from seed.business_data import Q_HNZZ
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES2_H, SALES_H, Tracker, make_tier
from tests.api.test_opportunities_api import new_opp

# 硬件 ¥100,000（成本 ¥70,000）+ 服务 ¥50,000（成本 ¥20,000）：毛利 40%
GOOD = [("hardware", 1, 7_000_000, 10_000_000), ("service", 1, 2_000_000, 5_000_000)]
# 毛利 10%，低于 25% 底线
LOW = [("hardware", 1, 9_000_000, 10_000_000)]


def create_quote(
    tracker: Tracker, tier: SolutionTier, opp_id: str | None = None, user: CurrentUser | None = None
) -> str:
    owner = user or DEMO_USERS[Role.SALES]
    with session_scope() as db:
        out = quote_service.create_from_tier(
            db,
            owner,
            pack="llm_deploy",
            tier=tier,
            opportunity_id=uuid.UUID(opp_id) if opp_id else None,
            idempotency_key=f"test:{uuid.uuid4().hex}",
        )
    tracker.quotes.append(out.id)
    return str(out.id)


def act(client: TestClient, quote_id: str, action: str, headers: dict[str, str] = SALES_H) -> dict:
    return client.post(f"/api/quotes/{quote_id}/{action}", headers=headers).json()


def test_full_lifecycle_creates_contract_and_commission(
    client: TestClient, tracker: Tracker
) -> None:
    opp = new_opp(client, tracker)
    qid = create_quote(tracker, make_tier(GOOD), opp["id"])
    submitted = act(client, qid, "submit")["data"]
    assert submitted["status"] == "approved" and submitted["approvals"] == []
    assert submitted["estimated_commission"] == 300_000 + 400_000  # 硬件 3% + 服务 8%

    illegal = act(client, qid, "accept")
    assert illegal["code"] == 42201 and illegal["data"]["rule"] == "quote_status_transition"

    assert act(client, qid, "send")["data"]["status"] == "sent"
    accepted = act(client, qid, "accept")["data"]
    assert accepted["status"] == "accepted" and accepted["contract_id"]

    opp_after = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert opp_after["stage"] == "won"

    contract = client.get(f"/api/contracts/{accepted['contract_id']}", headers=SALES_H).json()[
        "data"
    ]
    assert contract["code"].startswith("C-") and contract["amount"] == 15_000_000
    assert contract["commission"] == {"estimated": 700_000, "confirmed": 0}
    assert contract["status"] == "active" and contract["quote"]["id"] == qid


def test_detail_fields(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD))
    data = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert data["status"] == "draft" and data["tier_name"] == "标准版" and data["source"] == "agent"
    line = data["items"][0]
    assert line["subtotal_price"] == line["unit_price"] * line["qty"]
    assert data["contract_id"] is None and data["margin_rate"] == 0.4


def test_low_margin_goes_to_approval_and_reject_returns_draft(
    client: TestClient, tracker: Tracker
) -> None:
    qid = create_quote(tracker, make_tier(LOW))
    data = act(client, qid, "submit")["data"]
    assert data["status"] == "pending_approval"
    assert len(data["approvals"]) == 1 and "毛利 10.0%" in data["approvals"][0]["reason"]
    assert act(client, qid, "send")["data"]["rule"] == "quote_status_transition"

    pending = client.get("/api/approvals?status=pending&page_size=100", headers=MANAGER_H).json()
    approval = next(a for a in pending["data"]["items"] if a["target"]["id"] == qid)
    assert approval["target_type"] == "quote" and approval["ai_suggestion"]
    r = client.post(
        f"/api/approvals/{approval['id']}/decide",
        json={"decision": "reject", "comment": "请调整配置"},
        headers=MANAGER_H,
    )
    assert r.json()["data"]["status"] == "rejected"
    detail = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert detail["status"] == "draft"
    assert detail["approvals"][0]["approver"]["name"] == "李薇"
    assert detail["approvals"][0]["comment"] == "请调整配置"
    # 驳回后可以重新提交，再走一次审批
    assert act(client, qid, "submit")["data"]["status"] == "pending_approval"


def test_discount_over_limit_needs_approval(client: TestClient, tracker: Tracker) -> None:
    # 目录价 ¥200,000，成交 ¥170,000：折扣 15% > 10%（毛利仍有 41%）
    tier = make_tier([("software", 1, 10_000_000, 20_000_000)], total_price=17_000_000)
    data = act(client, create_quote(tracker, tier), "submit")["data"]
    assert data["status"] == "pending_approval" and "折扣 15.0%" in data["approvals"][0]["reason"]


def test_customer_reject(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD))
    act(client, qid, "submit")
    act(client, qid, "send")
    assert act(client, qid, "reject")["data"]["status"] == "rejected"
    assert act(client, qid, "submit")["data"]["rule"] == "quote_status_transition"


def test_quote_permission(client: TestClient, tracker: Tracker) -> None:
    qid = create_quote(tracker, make_tier(GOOD), user=EXTRA_SALES)
    r = client.get(f"/api/quotes/{qid}", headers=SALES_H)
    assert r.status_code == 404 and r.json()["code"] == 40401
    assert act(client, qid, "submit")["code"] == 40401
    assert client.get(f"/api/quotes/{qid}", headers=MANAGER_H).json()["code"] == 0
    assert client.get(f"/api/quotes/{qid}", headers=SALES2_H).json()["code"] == 0


def test_list_filters(client: TestClient) -> None:
    r = client.get("/api/quotes?status=pending_approval&q=华南", headers=SALES_H).json()["data"]
    assert str(Q_HNZZ) in {q["id"] for q in r["items"]}
    hnzz = next(q for q in r["items"] if q["id"] == str(Q_HNZZ))
    assert hnzz["margin_rate"] == pytest.approx(0.228, abs=0.0005) and hnzz["tier_name"] == "经济版"
    assert client.get("/api/quotes?status=unknown", headers=SALES_H).json()["code"] == 40001
    by_opp = client.get(f"/api/quotes?opportunity_id={demo_id('opp:hnzz')}", headers=SALES_H)
    assert all(q["opportunity"]["name"] == "质检助手" for q in by_opp.json()["data"]["items"])


def _accepted_contract(client: TestClient, tracker: Tracker) -> dict:
    qid = create_quote(tracker, make_tier(GOOD))
    for action in ("submit", "send", "accept"):
        act(client, qid, action)
    cid = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]["contract_id"]
    return client.get(f"/api/contracts/{cid}", headers=SALES_H).json()["data"]


def test_payment_confirms_commission(client: TestClient, tracker: Tracker) -> None:
    contract = _accepted_contract(client, tracker)
    url = f"/api/contracts/{contract['id']}/payments"
    r = client.post(url, json={"amount": 1}, headers=SALES_H)
    assert r.status_code == 403 and r.json()["code"] == 40301
    paid = client.post(url, json={"amount": 6_000_000}, headers=MANAGER_H).json()["data"]
    assert paid["paid_ratio"] == 0.4 and paid["commission"]["confirmed"] == 280_000
    assert paid["status"] == "active"
    over = client.post(url, json={"amount": 9_000_001}, headers=MANAGER_H).json()
    assert over["code"] == 42201 and over["data"]["rule"] == "payment_exceeds_balance"
    assert client.post(url, json={"amount": 0}, headers=MANAGER_H).json()["code"] == 40001
    admin = client.post(url, json={"amount": 1}, headers=ADMIN_H).json()
    assert admin["code"] == 40301 and admin["data"]["rule"] == "role_forbidden"
    done = client.post(url, json={"amount": 9_000_000}, headers=MANAGER_H).json()["data"]
    assert done["status"] == "paid" and done["commission"]["confirmed"] == 700_000


def test_contract_list_summary_and_scope(client: TestClient) -> None:
    data = client.get("/api/contracts", headers=SALES_H).json()["data"]
    codes = {c["customer"]["name"]: c for c in data["items"] if c["customer"]}
    assert (
        codes["粤海物流集团"]["paid_ratio"] == 0.4 and codes["粤海物流集团"]["status"] == "active"
    )
    assert codes["南山教育集团"]["status"] == "paid"
    s = data["summary"]
    assert s["unpaid_amount"] >= 81_000_000 - 32_400_000
    assert s["estimated_commission"] >= s["confirmed_commission"] > 0
    paid_only = client.get("/api/contracts?status=paid", headers=SALES_H).json()["data"]
    assert all(c["status"] == "paid" for c in paid_only["items"])
    assert paid_only["summary"] == s  # summary 不受 status 筛选影响
    assert client.get("/api/contracts", headers=SALES2_H).json()["data"]["total"] == 0


def test_contract_detail_not_visible(client: TestClient) -> None:
    r = client.get(f"/api/contracts/{demo_id('contract:yuehai')}", headers=SALES2_H)
    assert r.status_code == 404 and r.json()["code"] == 40401
    assert client.get(f"/api/contracts/{uuid.uuid4()}", headers=ADMIN_H).json()["code"] == 40401


def test_list_quotes_filter_by_customer(client: TestClient) -> None:
    """客户详情页按客户查报价单；看不到的客户返回空列表而不是报错。"""
    from seed.data import C_HNZZ, C_PC3H

    mine = client.get("/api/quotes", params={"customer_id": str(C_HNZZ)}, headers=SALES_H).json()
    assert mine["code"] == 0
    assert mine["data"]["items"] and all(
        q["customer"]["id"] == str(C_HNZZ) for q in mine["data"]["items"]
    )
    other = client.get("/api/quotes", params={"customer_id": str(C_PC3H)}, headers=SALES_H).json()
    assert other["code"] == 0 and other["data"]["items"] == []
