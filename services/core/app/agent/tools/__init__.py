"""工具注册表（开发规范 §6.2）。"""

from app.agent.tools.base import (
    INJECTED_ARGS,
    ToolContext,
    ToolResult,
    ToolSpec,
    inject_system_args,
    run_tool,
)
from app.agent.tools.context_tools import CONTEXT_TOOLS
from app.agent.tools.crm_tools import CRM_TOOLS
from app.agent.tools.material_tools import MATERIAL_TOOLS
from app.agent.tools.policy_tools import POLICY_TOOLS
from app.agent.tools.solution_tools import SOLUTION_TOOLS
from app.common.auth import Role

TOOLS: dict[str, ToolSpec] = {
    t.name: t for t in [*CRM_TOOLS, *MATERIAL_TOOLS, *CONTEXT_TOOLS, *SOLUTION_TOOLS, *POLICY_TOOLS]
}

# 对话里交给模型自主调用（function calling）的工具；出方案链路的工具由状态图按固定顺序调用
CHAT_TOOL_NAMES: tuple[str, ...] = (
    "search_customer",
    "get_customer_context",
    "get_meddic",
    "add_followup",
    "digest_material",
    "update_opportunity_stage",
    "create_task",
    "submit_expense",
    "pipeline_summary",
    "calc_commission",
    "search_policy",
    "list_pending_approvals",
    "decide_approval",
)
# 按角色收窄可见工具（契约 §0）：管理员对业务数据只读；审批只有主管能做。service 层仍会再校验一次
READ_ONLY_TOOLS = frozenset(
    {
        "search_customer",
        "get_customer_context",
        "get_meddic",
        "pipeline_summary",
        "calc_commission",
        "search_policy",
    }
)


MANAGER_ONLY_TOOLS = frozenset({"list_pending_approvals", "decide_approval"})


def chat_tools_for(role: Role) -> list[ToolSpec]:
    names = [n for n in CHAT_TOOL_NAMES if n not in MANAGER_ONLY_TOOLS or role == Role.MANAGER]
    if role == Role.ADMIN:
        names = [n for n in names if n in READ_ONLY_TOOLS]
    return [TOOLS[n] for n in names]


__all__ = [
    "INJECTED_ARGS",
    "TOOLS",
    "ToolContext",
    "ToolResult",
    "ToolSpec",
    "chat_tools_for",
    "inject_system_args",
    "run_tool",
]
