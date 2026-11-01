"""出方案时关联客户 / 商机，并决定用哪个行业包。

没有从商机进入时，按用户这句话里提到的客户关联：只在自己负责的客户里找，唯一匹配才关联；
该客户恰好只有一个进行中的商机时一并关联商机（行业包随商机产品线）。
但销售在输入框手选了行业包、又和那个商机的产品线对不上时，说明是同一客户的新项目：
以手选为准，不关联商机，并在回复开头说明（回归：选软件外包却被带进电脑采购流程）。
"""

import logging
from typing import Any

from sqlalchemy import select

from app.agent.deps import AgentDeps
from app.agent.state import AgentState
from app.common.errors import BizError
from app.crm.models import Opportunity
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import customer_service
from app.packs.registry import get_pack

logger = logging.getLogger(__name__)


def request_text(state: AgentState) -> str:
    """出方案用的需求文字：用户原话；对话循环转入时附上模型结合上文整理的需求（补全了指代）。"""
    text = state.get("user_message", "")
    request = (state.get("solution_request") or "").strip()
    if request and request != text.strip():
        return f"{text}\n\n结合上文整理的需求：{request}" if text else request
    return text


def link_customer(deps: AgentDeps, state: AgentState) -> dict[str, Any]:
    """返回 customer_id / customer_name，唯一进行中商机时再加 opportunity_id / opportunity_name。"""
    if state.get("opportunity_id") or state.get("customer_id"):
        return {}
    try:
        return _match_customer(deps, state)
    except Exception:
        logger.warning("link_customer failed; quote will not be linked", exc_info=True)
        return {}


def _match_customer(deps: AgentDeps, state: AgentState) -> dict[str, Any]:
    with deps.ctx.session() as db:
        found = customer_service.find_mentioned(db, deps.ctx.user, request_text(state))
        if len(found) != 1:
            return {}
        customer = found[0]
        opps = db.execute(
            select(Opportunity.id, Opportunity.name).where(
                Opportunity.customer_id == customer.id,
                Opportunity.owner_id == deps.ctx.user.id,
                Opportunity.stage.not_in(FINAL_STAGES),
            )
        ).all()
        out: dict[str, Any] = {"customer_id": str(customer.id), "customer_name": customer.name}
        if len(opps) == 1:
            out["opportunity_id"] = str(opps[0].id)
            out["opportunity_name"] = opps[0].name
        return out


def _pack_name(pack_id: str | None) -> str:
    try:
        return get_pack(pack_id or "").name
    except BizError:
        return "未启用行业包的产品线"


def choose_pack(
    deps: AgentDeps, state: AgentState, linked: dict[str, Any]
) -> tuple[dict[str, Any], str, str | None]:
    """返回 (要写进状态的关联信息, 行业包, 给销售的提示)。

    从商机进入：商机产品线为准；自动关联的商机和手选行业包冲突：手选为准、不关联商机；
    都没有：手选 → 团队默认。resolve_pack 找不到可用行业包时抛 BizError。
    """
    linked = dict(linked)
    opp_name = linked.pop("opportunity_name", None)
    choice = state.get("pack_choice")
    if entered := state.get("opportunity_id"):
        return linked, deps.resolve_pack(entered), None
    auto = linked.get("opportunity_id")
    if not auto:
        return linked, choice or deps.resolve_pack(None), None
    try:
        opp_pack: str | None = deps.resolve_pack(auto)
    except BizError:
        if not choice:
            raise
        opp_pack = None
    if not choice or choice == opp_pack:
        return linked, opp_pack or "", None
    linked.pop("opportunity_id")
    notice = (
        f"{linked.get('customer_name', '这个客户')}已有进行中的商机「{opp_name}」"
        f"（{_pack_name(opp_pack)}），这次按你选的「{_pack_name(choice)}」当作新项目出方案，"
        "不关联那个商机；如果其实是同一个项目，请从该商机详情进入 AI 工作台。"
    )
    return linked, choice, notice
