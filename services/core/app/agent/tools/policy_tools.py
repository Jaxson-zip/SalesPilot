"""制度检索工具：RAG 查询，必须返回 sources；没有命中时 found=false。"""

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.rag import retriever


class SearchPolicyArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    pack_id: str | None = Field(default=None, description="当前行业包；为空时只查公司制度")


def search_policy(ctx: ToolContext, args: SearchPolicyArgs) -> ToolResult:
    scopes = retriever.scopes_for(args.pack_id)
    with ctx.session() as db:
        result = retriever.search(db, args.query, scopes, request_id=ctx.request_id)
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
