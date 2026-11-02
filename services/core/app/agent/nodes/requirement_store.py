"""出方案时的需求清单：和商机上保存的清单读写、判断确认后范围是否变了。"""

import logging
import uuid
from typing import Any

from app.agent.deps import AgentDeps
from app.agent.state import AgentState
from app.crm.services import requirement_service

logger = logging.getLogger(__name__)


def same_scope(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """交付端和功能模块（名称、复杂度、是否首期）是否一致。"""

    def scope(r: dict[str, Any]) -> tuple[list[str], list[tuple[str, str, bool]]]:
        mods = [
            (str(m.get("name")), str(m.get("complexity", "medium")), bool(m.get("must", True)))
            for m in r.get("modules") or []
            if isinstance(m, dict)
        ]
        return sorted(r.get("platforms") or []), sorted(mods)

    return scope(a) == scope(b)


def load_saved(deps: AgentDeps, opp_id: str | None, pack_id: str) -> dict[str, Any] | None:
    """从商机进入时读上次保存的需求清单（同一行业包才用），接着上次的往下走。"""
    if not opp_id:
        return None
    try:
        with deps.ctx.session() as db:
            rec = requirement_service.get_requirement(db, deps.ctx.user, uuid.UUID(opp_id))
    except Exception:
        logger.warning("load saved requirement failed", exc_info=True)
        return None
    return rec.model_dump(mode="json") if rec and rec.pack == pack_id else None


def save_to_opportunity(deps: AgentDeps, state: AgentState, **extra: Any) -> None:
    """把需求清单存到商机上（只有负责人本人能存；失败不影响出方案）。"""
    opp_id = state.get("opportunity_id")
    if not opp_id:
        return
    try:
        with deps.ctx.session() as db:
            requirement_service.save_requirement(
                db,
                deps.ctx.user,
                uuid.UUID(opp_id),
                pack=state.get("pack_id") or "",
                data=state.get("requirement") or {},
                confirmed=bool(state.get("requirement_confirmed")),
                **extra,
            )
    except Exception:
        logger.warning("save requirement failed", exc_info=True)
