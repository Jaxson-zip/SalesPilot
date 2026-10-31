"""转入出方案流程：对话循环里由模型判断「这句话要出方案」，交给状态图的固定流程。

出方案（配置 → 定价 → 毛利校验 → 重配 → 确认生成报价单）的每一步由规则代码计算，
不让模型自由调用；模型只负责判断时机，并结合上下文把需求说完整。
"""

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec

HANDOFF_TOOL = "start_solution"


class StartSolutionArgs(BaseModel):
    request: str = Field(
        min_length=1,
        max_length=2000,
        description=(
            "这轮方案需求的完整描述：结合上文把指代（「他们」「按刚才说的」）补全成客户名和具体需求，"
            "保留用户原话里的所有数字和要求，不要自己添加用户没说过的内容"
        ),
    )


def start_solution(ctx: ToolContext, args: StartSolutionArgs) -> ToolResult:
    return ToolResult(ok=True, summary="转入出方案流程", data={"request": args.request})


HANDOFF_TOOLS: list[ToolSpec] = [
    ToolSpec(
        HANDOFF_TOOL,
        "用户要出方案、做配置、报价、选型、估算算力 / 显存或开发工作量时调用；"
        "用户在回答上一轮方案的追问、或修改方案需求（模型、并发、预算、功能模块、端、工期、交付人数等）时也调用。"
        "调用后由出方案流程按规则计算配置和价格，并自己匹配客户、追问缺的信息："
        "调用前不用先查客户，不要自己追问需求细节，不要自己给配置、报价或估算数字，也不要输出文字",
        StartSolutionArgs,
        start_solution,
    ),
]
