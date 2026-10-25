"""图运行时依赖：当前用户的工具上下文、聊天模型、行业包解析。每个请求构造一份。"""

from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel

from app.agent.tools.base import ToolContext


@dataclass
class AgentDeps:
    ctx: ToolContext
    resolve_pack: Callable[[str | None], str]  # opportunity_id → pack_id
    llm: BaseChatModel | None = None  # None 时节点使用规则 / 模板兜底
    max_retries: int = 2
    max_tool_calls: int = 8
