"""PRD 规格书：模板版骨架、模型扩写（流式）、存储与过期提示、权限和行业包限制。"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.routers import opportunities as opp_router
from app.crm.services import prd_service, requirement_service
from app.crm.services.demo import DEMO_USERS
from app.packs.software_outsourcing import prd_generator
from app.packs.software_outsourcing.requirement import SoftwareRequirement
from tests.api.conftest import MANAGER_H, SALES2_H, SALES_H, Tracker
from tests.api.test_opportunities_api import new_opp
from tests.conftest import parse_sse

SALES = DEMO_USERS[Role.SALES]
REQ = {
    "project": "连锁门店预约小程序",
    "platforms": ["mini_program", "admin"],
    "modules": [
        {"key": "booking", "name": "在线预约", "complexity": "complex"},
        {"key": "report", "name": "数据报表", "must": False, "source": "inferred"},
    ],
    "deadline_weeks": 8,
    "budget": 15_000_000,
    "questions": ["门店有几家？"],
}


def _with_requirement(client: TestClient, tracker: Tracker, pack: str = "software_outsourcing"):
    opp = new_opp(client, tracker)
    with session_scope() as db:
        requirement_service.save_requirement(
            db, SALES, uuid.UUID(opp["id"]), pack=pack, data=REQ, confirmed=True
        )
    return opp


def _path(opp: dict[str, Any]) -> str:
    return f"/api/opportunities/{opp['id']}/requirement/prd"


@pytest.fixture
def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opp_router, "model_available", lambda *_a: False)


def test_skeleton_has_scope_roles_and_no_price() -> None:
    req = SoftwareRequirement.model_validate(REQ)
    md = prd_generator.skeleton(req, title="预约小程序", customer="明理律所", confirmed=False)
    for part in (
        "## 2 交付范围",
        "| 在线预约 | 复杂 | 首期 | 客户提出 |",
        "二期",
        "## 8 待确认问题",
    ):
        assert part in md
    assert "运营管理员" in md and "期望工期：8 周" in md
    assert "¥" not in md and "15" not in md.split("期望工期")[0]  # 不写预算和价格


def test_finalize_strips_fence_and_adds_draft_note() -> None:
    out = prd_generator.finalize("```markdown\n# 标题\n\n正文\n```")
    assert out.startswith("# 标题\n\n> AI 生成的草案")
    assert "```" not in out


def test_template_when_model_unavailable(client: TestClient, tracker: Tracker, no_model: None):
    opp = _with_requirement(client, tracker)
    assert client.get(_path(opp), headers=SALES_H).json()["data"] is None
    r = client.post(_path(opp), headers=SALES_H)
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    assert [e for e, _ in events] == ["artifact", "done"]
    prd = events[0][1]["data"]
    assert prd["source"] == "template" and "在线预约" in prd["markdown"]
    saved = client.get(_path(opp), headers=SALES_H).json()["data"]
    assert saved["markdown"] == prd["markdown"] and saved["stale"] is False
    # 主管能看，不能生成
    assert client.get(_path(opp), headers=MANAGER_H).json()["data"]["confirmed"] is True
    assert client.post(_path(opp), headers=SALES2_H).status_code in (403, 404)
    # 需求清单改过 → 过期提示
    with session_scope() as db:
        requirement_service.save_requirement(
            db, SALES, uuid.UUID(opp["id"]), pack="software_outsourcing", data=REQ, confirmed=True
        )
    assert client.get(_path(opp), headers=SALES_H).json()["data"]["stale"] is True


def test_rejects_other_pack_and_missing_requirement(
    client: TestClient, tracker: Tracker, no_model: None
) -> None:
    bare = new_opp(client, tracker)
    r = client.post(_path(bare), headers=SALES_H)
    assert r.status_code == 400 and "需求清单" in r.json()["message"]
    other = _with_requirement(client, tracker, pack="llm_deploy")
    r = client.post(_path(other), headers=SALES_H)
    assert r.status_code == 400 and "软件外包" in r.json()["message"]


class FakeStream:
    def __init__(self, pieces: list[str], fail: bool = False) -> None:
        self.pieces, self.fail = pieces, fail

    def stream(self, _messages: Any):
        for p in self.pieces:
            yield AIMessageChunk(content=p)
        if self.fail:
            raise RuntimeError("gateway down")


@pytest.mark.parametrize(
    ("llm", "source"),
    [
        (FakeStream(["# 预约小程序\n\n", "## 1 项目背景"]), "ai"),
        (FakeStream(["# 半"], True), "template"),
    ],
)
def test_run_streams_then_saves(client: TestClient, tracker: Tracker, llm: Any, source: str):
    opp = _with_requirement(client, tracker)
    with session_scope() as db:
        job = prd_service.prepare(db, SALES, uuid.UUID(opp["id"]))
    events = list(prd_service.run(SALES, job, llm))
    names = [e["event"] for e in events]
    assert names[0] == "message.delta" and names[-2:] == ["artifact", "done"]
    prd = events[-2]["data"]["data"]
    assert prd["source"] == source
    if source == "ai":
        assert prd["markdown"].startswith("# 预约小程序\n\n> AI 生成的草案")
    else:  # 中途失败：用模板版覆盖已经输出的部分
        assert "## 2 交付范围" in prd["markdown"]
