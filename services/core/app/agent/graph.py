"""LangGraph 状态图（开发规范 §6.1）。

START → router
  ├─ chitchat   → respond
  ├─ crm_action → tool_agent（function calling 循环）
  │                 ├─ 要执行写工具 → confirm_action（interrupt）→ run_action → tool_agent
  │                 └─ 完成 → respond
  └─ solution   → parse_requirement
                    ├─ 缺信息 → ask_user → END
                    └─ configure → price → check_margin
                                    ├─ 不达标且 retry < 2 → configure（带调整提示）
                                    ├─ 不达标且 retry = 2 → respond
                                    └─ 达标 → confirm（interrupt）→ save_quote → respond
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.deps import AgentDeps
from app.agent.nodes.respond import make_respond
from app.agent.nodes.router import make_router, route_intent
from app.agent.nodes.solution import (
    make_ask_user,
    make_check_margin,
    make_configure,
    make_confirm,
    make_parse_requirement,
    make_price,
    make_save_quote,
    route_after_configure,
    route_after_confirm,
    route_after_margin,
    route_after_parse,
)
from app.agent.nodes.tool_loop import (
    make_confirm_action,
    make_run_action,
    make_tool_agent,
    route_after_tool_agent,
)
from app.agent.state import AgentState


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """每个请求按当前用户构造依赖并编译（编译开销很小），会话状态由 checkpointer 共享。"""
    g = StateGraph(AgentState)
    g.add_node("router", make_router(deps))
    g.add_node("tool_agent", make_tool_agent(deps))
    g.add_node("confirm_action", make_confirm_action(deps))
    g.add_node("run_action", make_run_action(deps))
    g.add_node("parse_requirement", make_parse_requirement(deps))
    g.add_node("ask_user", make_ask_user(deps))
    g.add_node("configure", make_configure(deps))
    g.add_node("price", make_price(deps))
    g.add_node("check_margin", make_check_margin(deps))
    g.add_node("confirm", make_confirm(deps))
    g.add_node("save_quote", make_save_quote(deps))
    g.add_node("respond", make_respond(deps))

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_intent, ["respond", "tool_agent", "parse_requirement"])
    g.add_conditional_edges("tool_agent", route_after_tool_agent, ["confirm_action", "respond"])
    g.add_edge("confirm_action", "run_action")
    g.add_edge("run_action", "tool_agent")
    g.add_conditional_edges(
        "parse_requirement", route_after_parse, ["ask_user", "configure", "respond"]
    )
    g.add_edge("ask_user", END)
    g.add_conditional_edges("configure", route_after_configure, ["price", "respond"])
    g.add_edge("price", "check_margin")
    g.add_conditional_edges("check_margin", route_after_margin, ["confirm", "configure", "respond"])
    g.add_conditional_edges("confirm", route_after_confirm, ["save_quote", "respond"])
    g.add_edge("save_quote", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)
