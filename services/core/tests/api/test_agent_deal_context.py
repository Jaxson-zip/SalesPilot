"""对话上下文里的「当前这单」：从 CRM 读最新状态放进系统提示，不靠模型记聊天记录。"""

import uuid
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from app.agent import service
from app.agent.deal_context import deal_brief
from app.agent.deps import AgentDeps
from app.agent.sse import iter_graph_events
from app.agent.tools import ToolContext
from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Contract, Quote
from app.crm.services.deal_state_service import get_deal_state
from app.crm.services.demo import DEMO_USERS
from seed.data import C_MINGLI, demo_id
from tests.scripted_llm import ScriptedModel

OPP_MINGLI = demo_id("opp:mingli")


def _ctx(role: Role = Role.SALES) -> ToolContext:
    return ToolContext(
        user=DEMO_USERS[role], session=session_scope, thread_id=f"t-{uuid.uuid4().hex[:8]}"
    )


def test_brief_for_opportunity_and_customer() -> None:
    text = deal_brief(_ctx(), str(OPP_MINGLI), None)
    assert text is not None
    assert "合同审查私有化" in text and "「方案报价」" in text
    assert f"商机 id：{OPP_MINGLI}" in text and f"客户 id：{C_MINGLI}" in text
    customer = deal_brief(_ctx(), None, str(C_MINGLI))
    assert customer is not None and "深圳明理律师事务所" in customer and "进行中商机" in customer
    # 读不到（不存在 / 无权限）就不放，不影响对话
    assert deal_brief(_ctx(), str(uuid.uuid4()), None) is None
    assert deal_brief(_ctx(), None, None) is None


def test_state_includes_contract_and_payments() -> None:
    sales = DEMO_USERS[Role.SALES]
    with session_scope() as db:
        row = db.execute(
            select(Contract.code, Quote.opportunity_id)
            .join(Quote, Contract.quote_id == Quote.id)
            .where(Quote.opportunity_id.is_not(None), Contract.owner_id == sales.id)
            .limit(1)
        ).first()
        assert row is not None, "演示数据里应有关联商机的合同"
        state = get_deal_state(db, sales, row.opportunity_id)
    assert state.contract is not None and state.contract.code == row.code
    assert state.quote is not None


def test_system_prompt_carries_the_deal() -> None:
    llm = ScriptedModel(script=[AIMessage(content="好的。")])
    deps = AgentDeps(ctx=_ctx(), resolve_pack=lambda _o: "llm_deploy", llm=llm)
    run = service.prepare_chat(deps, "这单下一步怎么推", OPP_MINGLI, checkpointer=InMemorySaver())
    events: list[dict[str, Any]] = list(
        iter_graph_events(run.graph, run.payload, run.config, run.thread_id)
    )
    assert events[-1]["event"] == "done"
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage)
    assert "当前这单" in system.content and "合同审查私有化" in system.content
