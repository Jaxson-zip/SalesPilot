"""客户时间线带上名下商机 / 报价的里程碑（2026-11-04 走查发现的回归用例）。

原来只查挂在客户上的动态：报价发出、客户接受、回款、开票在客户详情里都看不到。
"""

from fastapi.testclient import TestClient

from app.packs.base import SolutionTier
from tests.api.conftest import SALES_H, Tracker, make_tier
from tests.api.test_opportunities_api import new_opp
from tests.api.test_quotes_contracts_api import GOOD, act, create_quote


def _actions(client: TestClient, customer_id: str, related: bool) -> list[tuple[str, str]]:
    url = f"/api/activities?subject_type=customer&subject_id={customer_id}&limit=100"
    r = client.get(url + ("&related=true" if related else ""), headers=SALES_H)
    assert r.status_code == 200, r.text
    return [(a["subject_type"], a["action"]) for a in r.json()["data"]["items"]]


def test_customer_timeline_includes_deal_milestones(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    tier: SolutionTier = make_tier(GOOD)
    qid = create_quote(tracker, tier, opp["id"])
    assert act(client, qid, "submit")["code"] == 0
    assert act(client, qid, "send")["code"] == 0

    related = _actions(client, opp["customer"]["id"], related=True)
    assert ("quote", "send") in related
    assert ("opportunity", "create") in related
    assert ("quote", "submit") not in related  # 提交审批是内部步骤，不进客户时间线
    plain = _actions(client, opp["customer"]["id"], related=False)
    assert all(t == "customer" for t, _ in plain)
