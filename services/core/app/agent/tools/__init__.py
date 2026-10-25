"""工具注册表（开发规范 §6.2）。"""

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec, run_tool
from app.agent.tools.crm_tools import CRM_TOOLS
from app.agent.tools.policy_tools import POLICY_TOOLS
from app.agent.tools.solution_tools import SOLUTION_TOOLS

TOOLS: dict[str, ToolSpec] = {t.name: t for t in [*CRM_TOOLS, *SOLUTION_TOOLS, *POLICY_TOOLS]}

__all__ = ["TOOLS", "ToolContext", "ToolResult", "ToolSpec", "run_tool"]
