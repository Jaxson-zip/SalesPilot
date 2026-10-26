"""业务模块端到端测试（依据 docs/api/业务模块接口契约.md）。

每个用例都新建自己的数据（新商机、新报价、新报销），不改动演示数据。
运行：uv run --python 3.12 --with httpx --with pytest pytest tests/e2e -q
"""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import pytest

from test_stack import CORE, GATEWAY, WEB, _up, login, sse

pytestmark = pytest.mark.skipif(
    not (_up(f"{CORE}/health") and _up(f"{GATEWAY}/health")),
    reason="docker compose 环境没有启动",
)

# 最小的合法 PNG（1×1）和 PDF，用作票据
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000000020001e221bc330000000049454e44ae426082"
)
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def call(method: str, path: str, role: str, **kw: object) -> dict:
    r = httpx.request(method, f"{WEB}{path}", headers=login(role), timeout=30, **kw)  # type: ignore[arg-type]
    return r.json()


def ok(body: dict) -> dict:
    assert body["code"] == 0, body
    return body["data"]


def my_customer(role: str = "sales") -> dict:
    items = ok(call("GET", "/api/customers", role, params={"view": "mine"}))["items"]
    return next(c for c in items if c["name"] == "深圳明理律师事务所")


# ---------- 工作台 ----------


def test_dashboard_has_kpis_and_funnel() -> None:
    data = ok(call("GET", "/api/dashboard", "sales"))
    for key in ("won_amount_month", "open_opportunities", "pending_approvals", "estimated_commission_month"):
        assert isinstance(data[key], int), key
    assert {s["stage"] for s in data["funnel"]} >= {"lead", "qualified", "proposal", "negotiation", "won"}


# ---------- 商机 ----------


def test_opportunity_create_and_stage_flow() -> None:
    customer = my_customer()
    opp = ok(
        call(
            "POST",
            "/api/opportunities",
            "sales",
            json={"customer_id": customer["id"], "name": f"e2e 商机 {uuid.uuid4().hex[:6]}", "amount": 1_000_000},
        )
    )
    assert opp["stage"] == "lead"

    moved = ok(call("PATCH", f"/api/opportunities/{opp['id']}/stage", "sales", json={"stage": "qualified"}))
    assert moved["stage"] == "qualified"

    detail = ok(call("GET", f"/api/opportunities/{opp['id']}", "sales"))
    assert any(a["action"] == "stage_changed" for a in detail["activities"])

    ok(call("PATCH", f"/api/opportunities/{opp['id']}/stage", "sales", json={"stage": "lost", "lost_reason": "预算取消"}))
    final = call("PATCH", f"/api/opportunities/{opp['id']}/stage", "sales", json={"stage": "proposal"})
    assert final["code"] == 42201 and final["data"]["rule"] == "opportunity_stage_final"


def test_sales_cannot_create_opportunity_for_other_sales_customer() -> None:
    team = ok(call("GET", "/api/customers", "manager", params={"view": "team"}))["items"]
    other = next(c for c in team if c["name"] == "鹏城第三人民医院")
    body = call("POST", "/api/opportunities", "sales", json={"customer_id": other["id"], "name": "越权", "amount": 1})
    assert body["code"] == 40401


def test_pipeline_summary_weighted_amount() -> None:
    data = ok(call("GET", "/api/pipeline/summary", "manager", params={"view": "team"}))
    assert data["weighted_amount"] <= data["total_amount"]


# ---------- 报价 → 合同 → 提成 → 回款 ----------


def _agent_quote() -> dict:
    headers = login("sales")
    thread = f"e2e-{uuid.uuid4().hex[:8]}"
    message = "给明理律所出一份 Qwen3-32B 私有化方案，50 人并发，预算 40 万以内"
    list(sse("/api/agent/chat", {"thread_id": thread, "message": message}, headers))
    events = list(sse("/api/agent/resume", {"thread_id": thread, "decision": "approve"}, headers))
    return next(d["data"] for e, d in events if e == "artifact" and d["type"] == "quote")


def test_quote_lifecycle_creates_contract_and_commission() -> None:
    quote = _agent_quote()
    assert ok(call("POST", f"/api/quotes/{quote['id']}/submit", "sales"))["status"] == "approved"  # 毛利 29.4% ≥ 25%

    illegal = call("POST", f"/api/quotes/{quote['id']}/accept", "sales")
    assert illegal["code"] == 42201 and illegal["data"]["rule"] == "quote_status_transition"

    ok(call("POST", f"/api/quotes/{quote['id']}/send", "sales"))
    accepted = ok(call("POST", f"/api/quotes/{quote['id']}/accept", "sales"))
    assert accepted["status"] == "accepted" and accepted["contract_id"]

    contract = ok(call("GET", f"/api/contracts/{accepted['contract_id']}", "sales"))
    assert contract["amount"] == quote["total_price"]
    assert contract["commission"]["estimated"] > 0 and contract["commission"]["confirmed"] == 0

    # 销售不能登记回款；主管登记一半后，已确认提成 = 预估 × 50%
    assert call("POST", f"/api/contracts/{contract['id']}/payments", "sales", json={"amount": 1})["code"] == 40301
    half = contract["amount"] // 2
    paid = ok(call("POST", f"/api/contracts/{contract['id']}/payments", "manager", json={"amount": half}))
    assert paid["commission"]["confirmed"] == round(contract["commission"]["estimated"] * half / contract["amount"])
    over = call("POST", f"/api/contracts/{contract['id']}/payments", "manager", json={"amount": contract["amount"]})
    assert over["code"] == 42201 and over["data"]["rule"] == "payment_exceeds_balance"


# ---------- 报销 → 审批 ----------


def _new_expense(amount: int, headcount: int) -> dict:
    customer = my_customer()
    return ok(
        call(
            "POST",
            "/api/expenses",
            "sales",
            json={
                "type": "entertainment",
                "amount": amount,
                "headcount": headcount,
                "occurred_on": date.today().isoformat(),
                "participants": "客户：王律师；我方：张晨",
                "customer_id": customer["id"],
                "reason": "e2e 方案沟通晚餐",
                "idempotency_key": uuid.uuid4().hex,
            },
        )
    )


def _upload(expense_id: str, kind: str, name: str, content: bytes, mime: str) -> dict:
    files = {"file": (name, content, mime)}
    return call("POST", f"/api/expenses/{expense_id}/attachments", "sales", files=files, data={"kind": kind})


def test_expense_requires_invoice_and_receipt() -> None:
    expense = _new_expense(40_000, 4)
    missing = call("POST", f"/api/expenses/{expense['id']}/submit", "sales")
    assert missing["code"] == 42201 and missing["data"]["rule"] == "expense_missing_invoice"

    bad_type = _upload(expense["id"], "invoice", "a.exe", b"MZ", "application/octet-stream")
    assert bad_type["code"] == 40001


def test_over_limit_expense_goes_to_manager_approval() -> None:
    expense = _new_expense(86_000, 4)  # 人均 ¥215 > ¥150
    ok(_upload(expense["id"], "invoice", "invoice.pdf", PDF, "application/pdf"))
    ok(_upload(expense["id"], "receipt", "receipt.png", PNG, "image/png"))
    submitted = ok(call("POST", f"/api/expenses/{expense['id']}/submit", "sales"))
    assert submitted["status"] == "pending_approval"

    assert call("GET", "/api/approvals", "sales")["code"] == 40301

    pending = ok(call("GET", "/api/approvals", "manager", params={"status": "pending"}))["items"]
    approval = next(a for a in pending if a["target"]["id"] == expense["id"])
    assert len(approval["attachments"]) == 2

    ok(call("POST", f"/api/approvals/{approval['id']}/decide", "manager", json={"decision": "approve"}))
    again = call("POST", f"/api/approvals/{approval['id']}/decide", "manager", json={"decision": "reject"})
    assert again["code"] == 42201 and again["data"]["rule"] == "approval_already_decided"
    assert ok(call("GET", f"/api/expenses/{expense['id']}", "sales"))["status"] == "approved"


def test_attachment_download_respects_data_scope() -> None:
    expense = _new_expense(30_000, 2)
    att = ok(_upload(expense["id"], "invoice", "invoice.pdf", PDF, "application/pdf"))
    mine = httpx.get(f"{WEB}{att['url']}", headers=login("sales"), timeout=30)
    assert mine.status_code == 200 and mine.content.startswith(b"%PDF")


# ---------- 行业包配置 ----------


def test_product_lines_read_all_write_admin() -> None:
    assert ok(call("GET", "/api/product-lines", "sales"))["items"], "销售建商机要能选产品线"
    lines = ok(call("GET", "/api/product-lines", "admin"))["items"]
    assert call("PUT", f"/api/product-lines/{lines[0]['id']}", "sales", json={"enabled": True})["code"] == 40301
    assert {"pack", "enabled", "open_opportunities"} <= set(lines[0])
    bad = call("PUT", f"/api/product-lines/{lines[0]['id']}", "admin", json={"pack": "not_installed"})
    assert bad["code"] == 40001
