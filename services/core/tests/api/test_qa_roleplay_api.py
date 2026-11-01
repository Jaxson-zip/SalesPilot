"""2026-11-01 多角色压测发现的问题：每条一个回归用例。"""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.agent.deal_context import colleagues_note
from app.agent.prompts import role_limits
from app.agent.requirement_brief import missing_labels
from app.agent.tools import TOOLS, ToolContext, chat_tools_for, run_tool
from app.agent.tools.solution_tools import invalid_fields
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.services.codes import local_today
from app.crm.services.demo import DEMO_USERS
from app.packs.llm_deploy.requirement import LlmDeployRequirement
from seed.data import C_HNZZ
from tests.api.conftest import SALES_H


def _ctx(role: Role) -> ToolContext:
    return ToolContext(user=DEMO_USERS[role], session=session_scope, thread_id="t-qa")


def _run(role: Role, tool: str, args: dict) -> object:
    return run_tool(TOOLS[tool], _ctx(role), args, lambda *_: None)


def test_out_of_range_value_is_not_reported_as_missing() -> None:
    """并发填 100 万 / -10，原来追问「还需要确认：并发用户数」，像没听到用户说的数。"""
    data = {"model_name": "Qwen3-32B", "concurrency": 1_000_000}
    invalid = invalid_fields(LlmDeployRequirement, data)
    assert invalid == {"concurrency": "你给的是 1000000，不能超过 10000"}
    assert (
        "要大于 0"
        in invalid_fields(LlmDeployRequirement, {**data, "concurrency": -10})["concurrency"]
    )
    assert invalid_fields(LlmDeployRequirement, {"model_name": "Qwen3-32B"}) == {}  # 没填不算
    label = missing_labels("llm_deploy", ["concurrency"], invalid)[0]
    assert label.startswith("并发用户数") and "不能超过 10000" in label


def test_search_customer_falls_back_to_opportunity_name() -> None:
    """「质检助手那单丢了」：质检助手是商机名，原来只按客户名查，查不到就卡住。"""
    result = _run(Role.SALES, "search_customer", {"keyword": "质检助手"})
    assert result.ok and "华南智能制造" in result.summary
    assert result.data[0]["id"] == str(C_HNZZ) and result.data[0]["matched_opportunity"]
    other = _run(Role.SALES, "search_customer", {"keyword": "不存在的东西xyz"})
    assert other.summary == "没有匹配的客户或商机"


def test_list_contracts_answers_commission_and_overdue() -> None:
    """问「我这个月提成多少」，原来没有工具可查，只能让销售自己报合同明细。"""
    mine = _run(Role.SALES, "list_contracts", {})
    assert mine.ok and mine.data["contracts"] and "预估提成" in mine.summary
    assert all(c["owner"] == "张晨" for c in mine.data["contracts"])
    team = _run(Role.MANAGER, "list_contracts", {"owner_name": "张晨"})
    assert team.ok and {c["owner"] for c in team.data["contracts"]} == {"张晨"}
    # 筛选后的合计只算筛出的合同，不再带全团队的「本月新签」
    assert team.summary.startswith("筛出") and "本月新签" not in team.summary
    est = sum(c["estimated"] for c in team.data["contracts"])
    assert f"预估提成 ¥{est / 100:,.0f}" in team.summary
    nobody = _run(Role.MANAGER, "list_contracts", {"owner_name": "不存在"})
    assert "没有叫「不存在」的同事" in nobody.summary
    overdue = _run(Role.SALES, "list_contracts", {"overdue_only": True})
    assert all(c["overdue_amount"] > 0 for c in overdue.data["contracts"])


def test_team_targets_gives_monthly_per_person() -> None:
    result = _run(Role.MANAGER, "team_targets", {})
    assert result.ok and {r["name"] for r in result.data["rows"]} >= {"张晨"}
    assert "累计口径" in _run(Role.MANAGER, "pipeline_summary", {}).summary


def test_admin_has_read_only_contract_tools() -> None:
    names = {t.name for t in chat_tools_for(Role.ADMIN)}
    assert {"list_contracts", "team_targets"} <= names and "submit_expense" not in names


def test_role_limits_point_to_the_right_place() -> None:
    """主管转移客户被说成「找管理员」，管理员重置密码被说成「没有权限，找 IT」。"""
    assert "「客户」页" in role_limits(Role.MANAGER) and "不能审批自己" in role_limits(Role.MANAGER)
    admin = role_limits(Role.ADMIN)
    assert "重置密码" in admin and "不要建议找 IT" in admin and "不能提交报销" in admin
    assert "不要建议找管理员" in role_limits(Role.SALES)


def test_colleagues_note_lists_team() -> None:
    """主管说「以张晨的身份记跟进」，模型把销售张晨当成了客户方联系人。"""
    note = colleagues_note(_ctx(Role.MANAGER))
    assert note and "张晨（销售）" in note and "不是客户联系人" in note


def test_form_inputs_reject_absurd_values(client: TestClient) -> None:
    """金额超出 bigint 返回 500、1 万亿商机、1900 年预计成交、全空格任务标题、2999 年截止都能存。"""
    base = {"customer_id": str(C_HNZZ), "name": "QA 校验"}
    for amount in (2**63, 10**17):
        r = client.post("/api/opportunities", json={**base, "amount": amount}, headers=SALES_H)
        assert r.json()["code"] == 40001 and "100 亿" in r.json()["message"]
    old = {**base, "amount": 100, "expected_close_date": "1900-01-01"}
    r = client.post("/api/opportunities", json=old, headers=SALES_H)
    assert r.json()["code"] == 40001 and "日期不合理" in r.json()["message"]
    task = {"subject_type": "customer", "subject_id": str(C_HNZZ)}
    soon = (local_today() + timedelta(days=3)).isoformat() + "T10:00:00"
    r = client.post("/api/tasks", json={**task, "title": "   ", "due_at": soon}, headers=SALES_H)
    assert r.json()["message"] == "任务标题不能为空"
    far = {**task, "title": "QA", "due_at": "2999-01-01T00:00:00"}
    assert client.post("/api/tasks", json=far, headers=SALES_H).json()["code"] == 40001
