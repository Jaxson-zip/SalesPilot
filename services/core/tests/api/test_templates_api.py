"""GET /api/templates：模板文案 + 规则填入的数字；以及主管查待审批的 Agent 工具。"""

import json
import re

from fastapi.testclient import TestClient

from app.agent.tools import TOOLS, ToolContext, run_tool
from app.agent.tools.previews import confirm_preview
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.services.demo import DEMO_USERS
from app.rules import load_rules
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.api.test_expenses_approvals_api import new_expense, with_receipts


def test_templates_fill_numbers_from_rules(client: TestClient) -> None:
    data = client.get("/api/templates", headers=SALES_H).json()["data"]
    rules = load_rules()
    guides = {g["type"]: g for g in data["expense_guides"]}
    per_person = rules.expense.entertainment_per_person // 100
    assert f"人均 {per_person} 元" in guides["entertainment"]["standard"]
    assert guides["entertainment"]["attachments"] == ["发票", "小票"]
    assert "每晚 500 元" in guides["hotel"]["standard"] and "深圳" in guides["hotel"]["standard"]
    assert not re.search(r"\{[a-z_0-9]+\}", json.dumps(data, ensure_ascii=False))  # 占位符都已填好
    assert f"{rules.quote.valid_days} 天" in data["quote_terms"][0]
    # 付款方式按回款计划生成，不写死在文案里；行业包可以有自己的一套条款
    plan = "、".join(f"{s.name} {s.ratio * 100:g}%" for s in rules.payment.schedule)
    assert any(plan in t for t in data["quote_terms"])
    software = " ".join(data["pack_quote_terms"]["software_outsourcing"])
    assert "签约首付款 30%" in software and "到货" not in software
    assert data["pack_quote_terms"]["llm_deploy"] == data["quote_terms"]
    assert "正式合同" in data["contract_terms"][0]
    assert {t["type"] for t in data["expense_templates"]} == {
        "entertainment",
        "transport",
        "hotel",
        "other",
    }
    assert data["lost_reasons"] and data["task"] and data["followup"]


def test_ai_prompts_by_role(client: TestClient) -> None:
    def titles(headers: dict[str, str]) -> list[str]:
        data = client.get("/api/templates", headers=headers).json()["data"]
        return [p["title"] for p in data["ai_prompts"]]

    assert "对话报销" in titles(SALES_H)
    assert "待审批" in titles(MANAGER_H) and "对话报销" not in titles(MANAGER_H)
    assert "全公司漏斗" in titles(ADMIN_H)


def test_solution_prompt_follows_pack(client: TestClient) -> None:
    """出方案示例卡片标了 pack_example，每个行业包都给出自己的例句（前端按当前行业包替换）。"""
    prompts = client.get("/api/templates", headers=SALES_H).json()["data"]["ai_prompts"]
    assert [p["title"] for p in prompts if p["pack_example"]] == ["出方案报价"]
    packs = client.get("/api/packs", headers=SALES_H).json()["data"]
    examples = {p["id"]: p["example_prompt"] for p in packs}
    assert all(examples.values()) and len(set(examples.values())) == len(examples)
    assert "小程序" in examples["software_outsourcing"]


def test_templates_require_login(client: TestClient) -> None:
    r = client.get("/api/templates")
    assert r.status_code == 401 and r.json()["code"] == 40101


def _ctx(role: Role) -> ToolContext:
    return ToolContext(user=DEMO_USERS[role], session=session_scope, thread_id="t-tpl")


def test_manager_lists_pending_and_sees_target_in_preview(
    client: TestClient, tracker: Tracker
) -> None:
    eid = new_expense(client, tracker, amount=86_000)["id"]
    with_receipts(client, eid)
    code = client.post(f"/api/expenses/{eid}/submit", headers=SALES_H).json()["data"]["code"]

    result = run_tool(TOOLS["list_pending_approvals"], _ctx(Role.MANAGER), {}, lambda *_: None)
    assert result.ok
    mine = next(a for a in result.data if a["target"]["code"] == code)
    args = {"approval_id": mine["approval_id"], "decision": "approve"}
    preview = confirm_preview(_ctx(Role.MANAGER), "decide_approval", args)
    assert preview["target"].startswith(code) and preview["amount"] == 86_000
    assert preview["decision"] == "通过"


def test_sales_cannot_list_approvals() -> None:
    result = run_tool(TOOLS["list_pending_approvals"], _ctx(Role.SALES), {}, lambda *_: None)
    assert not result.ok and result.error and result.error["code"] == 40301


def test_rule_notes_use_rules_numbers(client: TestClient) -> None:
    notes = client.get("/api/templates", headers=SALES_H).json()["data"]["rule_notes"]
    rules = load_rules()
    commission = {i["label"]: i["value"] for i in notes["commission"]["items"]}
    assert commission["硬件提成"] == f"{rules.commission.rates['hardware'] * 100:g}%"
    assert "× 0.5" in commission["低毛利合同"]
    quote = {i["label"]: i["value"] for i in notes["quote"]["items"]}
    assert quote["毛利底线"] == "低于 25% 需主管审批" and quote["报价有效期"] == "30 天"
    expense = {i["label"]: i["value"] for i in notes["expense"]["items"]}
    assert expense["客户招待"] == "人均 ¥150" and "¥500/晚" in expense["差旅住宿"]
