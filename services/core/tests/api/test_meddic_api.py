"""MEDDIC 赢单要素：查看、负责人修改、按阶段的风险、规则评估、AI 评估（剧本模型）。"""

import uuid

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.services import meddic_service
from app.crm.services.demo import DEMO_USERS
from tests.api.conftest import MANAGER_H, SALES2_H, SALES_H, Tracker
from tests.scripted_llm import ScriptedModel, call


def _setup(client: TestClient, tracker: Tracker, stage: str = "lead") -> tuple[str, str]:
    body = {"name": f"MEDDIC测试-{uuid.uuid4().hex[:6]}", "level": "A"}
    cid = client.post("/api/customers", json=body, headers=SALES_H).json()["data"]["id"]
    tracker.customers.append(uuid.UUID(cid))
    opp = client.post(
        "/api/opportunities",
        json={"customer_id": cid, "name": "MEDDIC商机", "amount": 50_000_000},
        headers=SALES_H,
    ).json()["data"]
    if stage != "lead":
        r = client.patch(
            f"/api/opportunities/{opp['id']}/stage", json={"stage": stage}, headers=SALES_H
        )
        assert r.json()["code"] == 0, r.text
    return cid, opp["id"]


def test_default_all_missing_with_stage_risks(client: TestClient, tracker: Tracker) -> None:
    _cid, oid = _setup(client, tracker, "negotiation")
    data = client.get(f"/api/opportunities/{oid}/meddic", headers=MANAGER_H).json()["data"]
    assert data["score"] == 0
    assert data["items"][0]["key"] == "identify_pain"
    assert all(i["questions"] for i in data["items"])
    # 商务谈判阶段：之前各阶段要求的都应确认 → 全部 6 项都是风险
    assert set(data["risks"]) == {
        "痛点",
        "量化收益",
        "决策标准",
        "经济决策人",
        "决策流程",
        "内部支持者",
    }


def test_owner_updates_and_score(client: TestClient, tracker: Tracker) -> None:
    _cid, oid = _setup(client, tracker, "qualified")
    url = f"/api/opportunities/{oid}/meddic"
    body = {
        "items": {
            "identify_pain": {"status": "confirmed", "evidence": "合同审查靠人工，每月积压 200 份"},
            "economic_buyer": {"status": "partial", "evidence": "周律师可能拍板"},
        }
    }
    data = client.put(url, json=body, headers=SALES_H).json()["data"]
    assert data["score"] == round(100 * 1.5 / 6)
    pain = next(i for i in data["items"] if i["key"] == "identify_pain")
    assert pain["status"] == "confirmed" and pain["questions"] == [] and pain["updated_by"]
    assert data["risks"] == []  # 需求确认阶段只要求痛点
    # 不是负责人不能改
    assert client.put(url, json=body, headers=SALES2_H).json()["code"] == 40401  # 看不到
    assert client.put(url, json=body, headers=MANAGER_H).json()["code"] == 40301


def test_rule_assess_uses_followups_and_contacts(client: TestClient, tracker: Tracker) -> None:
    cid, oid = _setup(client, tracker)
    client.post(
        f"/api/customers/{cid}/contacts",
        json={"name": "周律师", "role": "decision_maker"},
        headers=SALES_H,
    )
    client.post(
        f"/api/customers/{cid}/followups",
        json={"type": "visit", "content": "客户说合同审查效率低，明年要走招标流程"},
        headers=SALES_H,
    )
    with session_scope() as db:
        out = meddic_service.assess(db, DEMO_USERS[Role.SALES], uuid.UUID(oid), None)
    keys = {i.key: i for i in out.items}
    assert out.source == "rule"
    assert keys["identify_pain"].status == "partial"
    assert keys["decision_process"].status == "partial"
    assert "周律师" in (keys["economic_buyer"].evidence or "")
    assert "内部支持者" in out.summary


def test_ai_assess_with_scripted_model(client: TestClient, tracker: Tracker) -> None:
    cid, oid = _setup(client, tracker)
    client.post(
        f"/api/customers/{cid}/followups",
        json={"type": "phone", "content": "李总说预算 80 万，他来拍板"},
        headers=SALES_H,
    )
    llm = ScriptedModel(
        script=[
            call(
                "MeddicAssessment",
                {
                    "items": [
                        {"key": "economic_buyer", "status": "confirmed", "evidence": "李总拍板"}
                    ],
                    "summary": "缺决策流程，下次问招标时间",
                },
                "m1",
            )
        ]
    )
    with session_scope() as db:
        out = meddic_service.assess(db, DEMO_USERS[Role.SALES], uuid.UUID(oid), llm)
    assert out.source == "ai" and out.items[0].key == "economic_buyer"
    assert "李总说预算" in llm.seen[0][-1].content


def test_assess_endpoint_falls_back(client: TestClient, tracker: Tracker) -> None:
    _cid, oid = _setup(client, tracker)
    r = client.post(f"/api/opportunities/{oid}/meddic/assess", headers=SALES_H)
    assert r.json()["code"] == 0
    assert r.json()["data"]["source"] in {"ai", "rule"}


def test_meddic_tool_for_chat() -> None:
    from app.agent.tools import TOOLS

    spec = TOOLS["get_meddic"]
    assert not spec.write
    assert AIMessage  # 工具只读，聊天里直接执行
