"""第三轮外部审查的回归测试：报价范围按档位固化、回款期次跟报价、有效期贯穿成交。"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Opportunity, Quote
from app.crm.services import quote_service, quote_snapshot
from app.crm.services.demo import DEMO_USERS
from app.packs.registry import get_configurator
from app.packs.software_outsourcing.requirement import SoftwareRequirement
from app.rules.loader import PaymentStage
from tests.api.conftest import SALES_H, Tracker, make_tier
from tests.api.test_quotes_contracts_api import GOOD, act, create_quote, new_opp

PACK = "software_outsourcing"
REQ = {
    "platforms": ["mini_program", "app", "admin"],
    "modules": [
        {"key": "account", "name": "用户注册登录"},
        {"key": "booking", "name": "在线预约排期"},
        {"key": "points", "name": "会员积分", "must": False},
    ],
}


def _software_quote(client: TestClient, tracker: Tracker, drop: str | None = None) -> str:
    """商机确认软件外包需求 → 经济版报价；drop：销售在明细里删掉的模块。"""
    opp = new_opp(client, tracker)
    record = {"pack": PACK, "confirmed": True, "data": REQ}
    with session_scope() as db:
        db.execute(
            update(Opportunity)
            .where(Opportunity.id == uuid.UUID(opp["id"]))
            .values(requirement=record)
        )
    tiers = get_configurator(PACK).configure(SoftwareRequirement.model_validate(REQ))
    tier = next(t for t in tiers if t.tier == "economy")
    if drop:
        kept = [i for i in tier.items if not i.name.startswith(drop)]
        tier = tier.model_copy(
            update={"items": kept, "total_price": sum(i.total_price for i in kept)}
        )
    user = DEMO_USERS[Role.SALES]
    with session_scope() as db:
        out = quote_service.create_from_tier(
            db, user, pack=PACK, tier=tier, opportunity_id=uuid.UUID(opp["id"]),
            idempotency_key=f"test:{uuid.uuid4().hex}",
        )  # fmt: skip
    tracker.quotes.append(out.id)
    return str(out.id)


def test_economy_scope_lists_only_quoted_parts(client: TestClient, tracker: Tracker) -> None:
    """回归：经济版只做首期模块、第一个客户端，项目范围却按整份需求列出二期功能和 App。"""
    qid = _software_quote(client, tracker, drop="在线预约排期")
    assert act(client, qid, "submit")["code"] == 0
    scope = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]["scope"]
    assert scope["platforms"] == ["mini_program", "admin"]
    assert scope["excluded_platforms"] == ["app"]
    assert [m["name"] for m in scope["modules"]] == ["用户注册登录"]
    assert scope["excluded_modules"] == ["在线预约排期", "会员积分"]  # 删掉的 + 二期的

    with session_scope() as db:
        status = db.get(Quote, uuid.UUID(qid)).status  # type: ignore[union-attr]
    if status == "approved":  # 分享页同一份范围
        token = client.post(f"/api/quotes/{qid}/share", headers=SALES_H).json()["data"]["token"]
        public = client.get(f"/api/public/quotes/{token}").json()["data"]["scope"]
        assert public["modules"] == ["用户注册登录"] and public["excluded_platforms"] == ["app"]


def test_old_snapshot_scope_is_recomputed_by_tier(client: TestClient, tracker: Tracker) -> None:
    """上一版快照存的是整份需求：读的时候按明细补算，不会把二期功能列进范围。"""
    qid = _software_quote(client, tracker)
    act(client, qid, "submit")
    with session_scope() as db:
        quote = db.get(Quote, uuid.UUID(qid))
        assert quote is not None
        quote.snapshot = {**(quote.snapshot or {}), "scope": REQ}
    scope = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]["scope"]
    assert "会员积分" in scope["excluded_modules"]
    assert all(m["name"] != "会员积分" for m in scope["modules"])


def test_contract_plan_follows_quote_not_new_rules(
    client: TestClient, tracker: Tracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """回归：报价写的是「预付 30%…」，管理员改成 50/50 后客户接受，合同按新比例拆期。"""
    opp = new_opp(client, tracker)
    qid = create_quote(tracker, make_tier(GOOD), opp["id"])
    detail = act(client, qid, "submit")["data"]
    with session_scope() as db:
        frozen = quote_snapshot.payment_schedule_of(db.get(Quote, uuid.UUID(qid)))  # type: ignore[arg-type]
    real = quote_service.rules_for

    def changed(quote: Quote):
        rules = real(quote)
        half = [
            PaymentStage(name="首付", ratio=0.5, due_days=0),
            PaymentStage(name="尾款", ratio=0.5, due_days=30),
        ]
        return rules.model_copy(
            update={"payment": rules.payment.model_copy(update={"schedule": half})}
        )

    monkeypatch.setattr(quote_service, "rules_for", changed)
    monkeypatch.setattr(quote_snapshot, "_rules", changed)
    act(client, qid, "send")
    cid = act(client, qid, "accept")["data"]["contract_id"]
    plan = client.get(f"/api/contracts/{cid}/payment-plan", headers=SALES_H).json()["data"]
    assert [i["name"] for i in plan["items"]] == [s.name for s in frozen]
    first = round(detail["total_price"] * frozen[0].ratio)
    assert plan["items"][0]["amount"] == first


def _expire(qid: str) -> None:
    with session_scope() as db:
        quote = db.get(Quote, uuid.UUID(qid))
        assert quote is not None
        quote.snapshot = {**(quote.snapshot or {}), "valid_until": "2020-01-31"}


def test_expired_quote_cannot_close_until_renewed(client: TestClient, tracker: Tracker) -> None:
    """回归：分享链接查过期，但「客户接受」和看板「按报价赢单」不查，过期报价照样生成合同。"""
    opp = new_opp(client, tracker)
    qid = create_quote(tracker, make_tier(GOOD), opp["id"])
    act(client, qid, "submit")
    early = act(client, qid, "renew")
    assert early["code"] == 42201 and early["data"]["rule"] == "quote_renew_not_allowed"
    _expire(qid)
    detail = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert detail["expired"] is True and detail["valid_until"] == "2020-01-31"
    sent = act(client, qid, "send")
    assert sent["code"] == 42201 and sent["data"]["rule"] == "quote_expired"
    url = f"/api/opportunities/{opp['id']}/stage"
    won = client.patch(url, json={"stage": "won", "quote_id": qid}, headers=SALES_H).json()
    assert won["code"] == 42201 and won["data"]["rule"] == "quote_expired"

    renewed = act(client, qid, "renew")["data"]
    assert renewed["status"] == "draft" and renewed["expired"] is False
    again = act(client, qid, "submit")["data"]
    assert date.fromisoformat(again["valid_until"]) >= date.today() + timedelta(days=1)
    act(client, qid, "send")
    assert act(client, qid, "accept")["data"]["status"] == "accepted"


def test_valid_until_fixed_after_submit(
    client: TestClient, tracker: Tracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """回归：详情的有效期按当前设置重新算，改了有效天数旧报价的日期跟着变。"""
    qid = create_quote(tracker, make_tier(GOOD))
    before = act(client, qid, "submit")["data"]["valid_until"]
    real = quote_snapshot._rules

    def longer(quote: Quote):
        rules = real(quote)
        return rules.model_copy(update={"quote": rules.quote.model_copy(update={"valid_days": 90})})

    monkeypatch.setattr(quote_snapshot, "_rules", longer)
    assert client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]["valid_until"] == before
