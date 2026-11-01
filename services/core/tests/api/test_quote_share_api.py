"""报价分享链接（接口契约 §35）：负责人生成 / 撤销，甲方免登录查看；不含成本，失效一律 40401。"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.common.db import session_scope
from app.crm.models import Activity, Notification, Quote, QuoteShare
from tests.api.conftest import MANAGER_H, SALES2_H, SALES_H, Tracker, make_tier
from tests.api.test_quotes_contracts_api import GOOD, LOW, act, create_quote


def _approved(client: TestClient, tracker: Tracker) -> str:
    qid = create_quote(tracker, make_tier(GOOD))
    assert act(client, qid, "submit")["data"]["status"] == "approved"
    return qid


def _share(client: TestClient, qid: str, headers: dict[str, str] = SALES_H) -> dict:
    return client.post(f"/api/quotes/{qid}/share", headers=headers).json()


def test_share_marks_sent_and_public_view_hides_cost(client: TestClient, tracker: Tracker) -> None:
    qid = _approved(client, tracker)
    share = _share(client, qid)
    assert share["code"] == 0, share
    token = share["data"]["token"]
    assert share["data"]["path"] == f"/share/q/{token}"
    assert client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]["status"] == "sent"
    assert _share(client, qid)["data"]["token"] == token  # 重复点返回同一条

    r = client.get(f"/api/public/quotes/{token}")  # 不带登录
    assert r.status_code == 200, r.text
    view = r.json()["data"]
    assert view["status"] == "sent" and view["total_price"] == 15_000_000
    assert view["list_price"] == 15_000_000 and len(view["items"]) == 2
    assert view["terms"] and view["customer_name"]
    flat = r.text
    for secret in ("unit_cost", "total_cost", "margin", "commission", "subtotal_cost"):
        assert secret not in flat


def test_first_view_of_day_notifies_owner_once(client: TestClient, tracker: Tracker) -> None:
    qid = _approved(client, tracker)
    token = _share(client, qid)["data"]["token"]
    client.get(f"/api/public/quotes/{token}", headers=SALES_H)  # 自己预览不算
    client.get(f"/api/public/quotes/{token}")
    client.get(f"/api/public/quotes/{token}")
    state = client.get(f"/api/quotes/{qid}/share", headers=SALES_H).json()["data"]
    assert state["view_count"] == 2 and state["last_viewed_at"]
    with session_scope() as db:
        views = db.scalars(
            select(Activity).where(
                Activity.subject_id == uuid.UUID(qid), Activity.action == "viewed"
            )
        ).all()
        notes = db.scalars(
            select(Notification).where(
                Notification.link == f"/quotes/{qid}", Notification.type == "quote_viewed"
            )
        ).all()
        assert len(views) == 1 and len(notes) == 1  # 同一天只提醒一次


def test_revoked_or_expired_link_is_404(client: TestClient, tracker: Tracker) -> None:
    qid = _approved(client, tracker)
    token = _share(client, qid)["data"]["token"]
    assert client.delete(f"/api/quotes/{qid}/share", headers=SALES_H).json()["code"] == 0
    assert client.get(f"/api/public/quotes/{token}").json()["code"] == 40401
    assert client.get(f"/api/quotes/{qid}/share", headers=SALES_H).json()["data"] is None

    token2 = _share(client, qid)["data"]["token"]  # 撤销后可以重新生成，旧链接仍然失效
    assert token2 != token
    with session_scope() as db:
        past = datetime.now(UTC) - timedelta(minutes=1)
        db.execute(update(QuoteShare).where(QuoteShare.token == token2).values(expires_at=past))
    assert client.get(f"/api/public/quotes/{token2}").json()["code"] == 40401
    assert client.get("/api/public/quotes/not-a-real-token-123").json()["code"] == 40401


def test_share_requires_approved_quote(client: TestClient, tracker: Tracker) -> None:
    draft = create_quote(tracker, make_tier(GOOD))
    r = _share(client, draft)
    assert r["code"] == 42201 and r["data"]["rule"] == "quote_share_status"
    pending = create_quote(tracker, make_tier(LOW))
    act(client, pending, "submit")  # 低毛利 → 待主管审批
    assert _share(client, pending)["data"]["rule"] == "quote_share_status"


def test_only_owner_can_share(client: TestClient, tracker: Tracker) -> None:
    qid = _approved(client, tracker)
    assert _share(client, qid, SALES2_H)["code"] == 40401  # 别人的报价看不到
    assert _share(client, qid, MANAGER_H)["code"] == 40301  # 主管看得到，但不是负责人
    assert client.delete(f"/api/quotes/{qid}/share", headers=SALES2_H).json()["code"] == 40401
    assert client.get(f"/api/quotes/{qid}/share", headers=MANAGER_H).json()["code"] == 0


def test_software_quote_terms_follow_pack(client: TestClient, tracker: Tracker) -> None:
    """回归：软件外包报价的条款原来是硬件的（到货验收、原厂质保），付款比例和里程碑回款计划对不上。"""
    qid = _approved(client, tracker)
    with session_scope() as db:
        db.execute(
            update(Quote).where(Quote.id == uuid.UUID(qid)).values(pack="software_outsourcing")
        )
    token = _share(client, qid)["data"]["token"]
    terms = " ".join(client.get(f"/api/public/quotes/{token}").json()["data"]["terms"])
    assert "签约首付款 30%、原型与 UI 确认款 30%、上线验收款 30%、质保尾款 10%" in terms
    for hardware in ("到货", "原厂质保", "运输"):
        assert hardware not in terms
