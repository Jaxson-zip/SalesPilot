"""日报统计口径（2026-11-03 实测问题的回归用例）。

原来按操作日志数「新建 + 提交」，同一张报价算两次；报价发出后商机自动推进到方案报价，
没有经过阶段接口，阶段推进没算进去。现在按业务数据统计。
"""

from fastapi.testclient import TestClient

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.services import report_service
from app.crm.services.codes import local_today
from app.crm.services.demo import DEMO_USERS
from app.packs.base import SolutionTier
from tests.api.conftest import Tracker, make_tier
from tests.api.test_opportunities_api import new_opp
from tests.api.test_quotes_contracts_api import GOOD, act, create_quote

SALES = DEMO_USERS[Role.SALES]


def _stats() -> tuple[int, int]:
    with session_scope() as db:
        s = report_service.collect_facts(db, SALES.id, local_today()).stats
    return s.quotes, s.stage_changes


def test_quote_counted_once_and_auto_stage_counted(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    quotes, stages = _stats()
    tier: SolutionTier = make_tier(GOOD)
    qid = create_quote(tracker, tier, opp["id"])
    assert act(client, qid, "submit")["data"]["status"] == "approved"
    assert _stats() == (quotes + 1, stages)  # 新建 + 提交只算 1 张；草稿不推进商机
    assert act(client, qid, "send")["code"] == 0  # 发给客户：商机自动推进到方案报价
    assert _stats() == (quotes + 1, stages + 1)
