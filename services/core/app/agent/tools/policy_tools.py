"""制度检索工具：RAG 查询，必须返回 sources；没有命中时 found=false。

知识库不可用（没有配置 Embedding 模型、网关报错）时不把错误抛给模型，而是返回 rules.yaml
里的规则数字：报销标准、提成比例等本来就以规则为准，知识库只提供条款出处。
"""

import logging

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.common.errors import BizError
from app.crm.services.rule_notes import rule_notes
from app.packs.registry import list_packs
from app.rag import retriever
from app.rules import load_rules

logger = logging.getLogger("core.agent")


def _pack_choices() -> str:
    return "、".join(f"{p.id}（{p.name}）" for p in list_packs().values())


class SearchPolicyArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    # 系统注入：当前会话的行业包（关联商机的产品线 → 团队默认产品线 → 系统默认）
    pack_id: str | None = Field(default=None, description="当前行业包；为空时只查公司制度")
    pack: str | None = Field(
        default=None,
        description=f"用户明确点名的行业包，可选：{_pack_choices()}。"
        "用户没点名就不填，按当前会话的行业包检索",
    )


def _scope(args: SearchPolicyArgs) -> tuple[str | None, str]:
    """实际检索的行业包：用户点名的优先，其次是当前会话的；返回 (pack_id, 范围说明)。"""
    packs = list_packs()
    pack = args.pack if args.pack in packs else args.pack_id
    label = f"「{packs[pack].name}」行业资料和公司制度" if pack in packs else "公司制度"
    return pack, label


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
    pack, label = _scope(args)
    scopes = retriever.scopes_for(pack)
    try:
        with ctx.session() as db:
            result = retriever.search(db, args.query, scopes, request_id=ctx.request_id)
    except BizError as exc:
        return _rules_fallback(exc)
    data = {**result.model_dump(), "pack_id": pack, "searched": label}
    if not result.found:
        # 只说明这个范围里没命中：不能说成平台没有这份文档
        summary = f"在{label}里没有检索到相关内容（只代表这次检索范围内没命中）"
        return ToolResult(ok=True, summary=summary, data=data)
    names = "、".join(dict.fromkeys(s.doc_name for s in result.sources))
    return ToolResult(
        ok=True, summary=f"在{label}里命中 {len(result.sources)} 条：{names}", data=data
    )


POLICY_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "search_policy",
        "检索公司制度与行业知识（返回出处）。默认按当前会话的行业包查；"
        "用户明确问某个行业包（如软件外包）时填 pack",
        SearchPolicyArgs,
        search_policy,
    ),
]
