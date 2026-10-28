"""制度检索工具：RAG 查询，必须返回 sources；没有命中时 found=false。

知识库不可用（没有配置 Embedding 模型、网关报错）时不把错误抛给模型，而是返回 rules.yaml
里的规则数字：报销标准、提成比例等本来就以规则为准，知识库只提供条款出处。
"""

import logging

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.common.errors import BizError
from app.crm.services.rule_notes import rule_notes
from app.rag import retriever
from app.rules import load_rules

logger = logging.getLogger("core.agent")


class SearchPolicyArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    pack_id: str | None = Field(default=None, description="当前行业包；为空时只查公司制度")


def _rules_fallback(exc: BizError) -> ToolResult:
    logger.warning("search_policy: knowledge base unavailable (%s), fallback to rules", exc)
    notes = {
        n.title: [f"{i.label}：{i.value}" for i in n.items] + ([n.note] if n.note else [])
        for n in rule_notes(load_rules()).values()
    }
    return ToolResult(
        ok=True,
        summary="制度知识库暂未启用，已返回系统规则中的标准（没有条款出处）",
        data={"found": False, "sources": [], "kb_available": False, "rules": notes},
    )


def search_policy(ctx: ToolContext, args: SearchPolicyArgs) -> ToolResult:
    scopes = retriever.scopes_for(args.pack_id)
    try:
        with ctx.session() as db:
            result = retriever.search(db, args.query, scopes, request_id=ctx.request_id)
    except BizError as exc:
        return _rules_fallback(exc)
    if not result.found:
        return ToolResult(ok=True, summary="制度中未找到相关规定", data=result.model_dump())
    names = "、".join(dict.fromkeys(s.doc_name for s in result.sources))
    return ToolResult(
        ok=True, summary=f"命中 {len(result.sources)} 条：{names}", data=result.model_dump()
    )


POLICY_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "search_policy", "检索公司制度与行业知识（返回出处）", SearchPolicyArgs, search_policy
    ),
]
