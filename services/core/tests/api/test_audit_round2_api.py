"""第二轮外部审查的回归测试：报价幂等、报价快照、回款防重复、单号并发、正式模式降级。"""

import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.common import auth
from app.common.auth import CurrentUser, Role
from app.common.db import session_scope
from app.common.errors import BizError
from app.crm.models import Opportunity, Quote
from app.crm.services import quote_service, template_service
from app.crm.services.codes import next_code
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import MANAGER_H, SALES_H, Tracker, make_tier
from tests.api.test_payments_api import _pay
from tests.api.test_quotes_contracts_api import (
    GOOD,
    _accepted_contract,
    act,
    create_quote,
    new_opp,
)


def test_same_key_different_content_conflicts(tracker: Tracker) -> None:
    """同一幂等键：内容一样返回原单（重试），内容不一样报 40901，不再悄悄返回旧单。"""
    key = f"test:{uuid.uuid4().hex}"
    tier = make_tier(GOOD)
    user = DEMO_USERS[Role.SALES]
    with session_scope() as db:
        cid = db.scalars(select(Quote.customer_id).where(Quote.owner_id == user.id)).first()
        first = quote_service.create_from_tier(
            db, user, pack="llm_deploy", tier=tier, opportunity_id=None,
            idempotency_key=key, customer_id=cid,
        )  # fmt: skip
        tracker.quotes.append(first.id)
        again = quote_service.create_from_tier(
            db, user, pack="llm_deploy", tier=tier, opportunity_id=None,
            idempotency_key=key, customer_id=cid,
        )  # fmt: skip
        assert again.id == first.id
        changed = tier.model_copy(update={"items": tier.items[:1]})
        with pytest.raises(BizError) as exc:
            quote_service.create_from_tier(
                db, user, pack="llm_deploy", tier=changed, opportunity_id=None,
                idempotency_key=key, customer_id=cid,
            )  # fmt: skip
        assert exc.value.code == 40901


def _set_requirement(opp_id: str, modules: list[str]) -> None:
    record = {
        "pack": "llm_deploy",
        "confirmed": True,
        "data": {"platforms": ["web"], "modules": [{"name": m} for m in modules], "team_size": 3},
    }
    with session_scope() as db:
        db.execute(
            update(Opportunity)
            .where(Opportunity.id == uuid.UUID(opp_id))
            .values(requirement=record)
        )


def test_submitted_quote_keeps_scope_and_terms(
    client: TestClient, tracker: Tracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """回归：分享页 / 打印版读商机当前需求和当前条款，改需求后旧报价的范围跟着变了。"""
    opp = new_opp(client, tracker)
    _set_requirement(opp["id"], ["会员积分"])
    qid = create_quote(tracker, make_tier(GOOD), opp["id"])
    draft = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert [m["name"] for m in draft["scope"]["modules"]] == ["会员积分"]
    terms = draft["terms"]
    assert act(client, qid, "submit")["data"]["status"] == "approved"

    _set_requirement(opp["id"], ["服务项目展示"])  # 之后改了需求和条款模板
    monkeypatch.setattr(template_service, "quote_terms", lambda _pack: ["新条款"])
    detail = client.get(f"/api/quotes/{qid}", headers=SALES_H).json()["data"]
    assert [m["name"] for m in detail["scope"]["modules"]] == ["会员积分"]
    assert detail["terms"] == terms
    token = client.post(f"/api/quotes/{qid}/share", headers=SALES_H).json()["data"]["token"]
    view = client.get(f"/api/public/quotes/{token}").json()["data"]
    assert view["scope"]["modules"] == ["会员积分"] and view["terms"] == terms

    # 草稿还没发出去：跟着当前需求和模板
    other = create_quote(tracker, make_tier(GOOD), opp["id"])
    live = client.get(f"/api/quotes/{other}", headers=SALES_H).json()["data"]
    assert [m["name"] for m in live["scope"]["modules"]] == ["服务项目展示"]
    assert live["terms"] == ["新条款"]


def test_payment_retry_is_recorded_once(client: TestClient, tracker: Tracker) -> None:
    """回归：第一次已入账但页面没收到响应，再点一次会多记一笔、多确认提成。"""
    cid = _accepted_contract(client, tracker)["id"]
    key = f"pay-{uuid.uuid4().hex}"
    first = _pay(client, cid, amount=1_000_000, idempotency_key=key)
    again = _pay(client, cid, amount=1_000_000, idempotency_key=key)
    assert first["code"] == 0 and again["code"] == 0
    assert again["data"]["paid_amount"] == 1_000_000
    rows = client.get(f"/api/contracts/{cid}/payments", headers=SALES_H).json()["data"]
    assert len(rows) == 1
    assert _pay(client, cid, amount=2_000_000, idempotency_key=key)["code"] == 40901
    assert _pay(client, cid, amount=1, idempotency_key="short")["code"] == 40001


def test_duplicate_reference_needs_review(client: TestClient, tracker: Tracker) -> None:
    """同一银行流水号再登记：拦下来提示核查；那笔冲正后可以重新登记。"""
    cid = _accepted_contract(client, tracker)["id"]
    ref = f"BK-{uuid.uuid4().hex[:10]}"
    assert _pay(client, cid, amount=1_000_000, reference_no=ref)["code"] == 0
    dup = _pay(client, cid, amount=500_000, reference_no=f" {ref} ")
    assert dup["code"] == 42201 and dup["data"]["rule"] == "payment_duplicate_reference"
    assert ref in dup["message"]

    pid = client.get(f"/api/contracts/{cid}/payments", headers=SALES_H).json()["data"][0]["id"]
    url = f"/api/contracts/{cid}/payments/{pid}/reverse"
    assert client.post(url, json={"reason": "金额录错"}, headers=MANAGER_H).json()["code"] == 0
    assert _pay(client, cid, amount=500_000, reference_no=ref)["code"] == 0


def test_concurrent_codes_do_not_collide() -> None:
    """回归：单号原来是「查当前最大号 + 1」，两个请求同时读到同一个最大号就会撞号。"""
    barrier = threading.Barrier(2)
    codes: list[str] = []
    errors: list[BaseException] = []
    prefix = f"Z{uuid.uuid4().hex[:3].upper()}"

    def worker() -> None:
        try:
            with session_scope() as db:
                barrier.wait()
                codes.append(next_code(db, Quote.code, prefix))
                time.sleep(0.2)  # 拿到号后事务还开着：旧实现下另一个请求也读到同一个最大号
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not errors and len(set(codes)) == 2, codes


def test_formal_mode_rejects_unverifiable_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """正式模式查不到账号状态时不再沿用 token 里的旧角色；演示模式保持原来的降级。"""
    user = CurrentUser(id=uuid.uuid4(), name="张晨", role=Role.SALES, team_id=None)
    token = auth.issue_token(user)

    def boom(_uid: uuid.UUID) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(auth, "_load_account", boom)
    assert auth.verify_token(token).id == user.id  # 演示模式
    formal = auth.get_settings().model_copy(update={"demo_login": False})
    monkeypatch.setattr(auth, "get_settings", lambda: formal)
    with pytest.raises(BizError) as exc:
        auth.verify_token(token)
    assert exc.value.code == 50301


def test_health_reports_memory_session_store(client: TestClient) -> None:
    """会话存储退回内存（重启会丢）时 /health 是 degraded，发布流水线的就绪检查会失败。"""
    body = client.get("/health").json()["data"]
    assert isinstance(body["persistent"], bool)
    if not body["persistent"]:
        assert body["status"] == "degraded"
