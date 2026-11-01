"""Agent 状态（LangGraph）。只放可 JSON 序列化的数据，便于 Postgres checkpointer 持久化。"""

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Intent = Literal["chitchat", "crm_action", "solution"]
# work：做方案 / 操作 CRM（默认）；learn：学习问答（新人带教，只读知识类工具）
Mode = Literal["work", "learn"]


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str  # 会话归属，resume 时校验
    user_message: NotRequired[str]
    mode: NotRequired[Mode]  # 会话模式，跨轮次保留
    material: NotRequired[str | None]  # 本轮上传的材料名（材料原文在用户消息里）
    samples: NotRequired[dict[str, Any] | None]  # 本轮上传的客户样例识别汇总（SampleSummary）
    opportunity_id: NotRequired[str | None]
    customer_id: NotRequired[str | None]  # 出方案时从对话里识别出的客户（唯一匹配才关联）
    customer_name: NotRequired[str | None]
    # 本轮给销售的关联说明（手选行业包和客户已有商机对不上时，按新项目处理）
    link_notice: NotRequired[str | None]
    intent: NotRequired[Intent]
    # 对话循环转入出方案时，模型结合上文整理的需求描述（补全指代，保留数字）
    solution_request: NotRequired[str | None]
    # 上一轮出方案时追问过、用户还没给的字段（本轮开始时从 missing 转存，提示模型用户可能在回答）
    prev_missing: NotRequired[list[str]]
    pack_id: NotRequired[str | None]
    # 没关联商机时销售在输入框选的行业包（跨轮次保留；关联了商机以商机产品线为准）
    pack_choice: NotRequired[str | None]
    requirement: NotRequired[dict[str, Any]]  # 跨轮次累积的需求草稿
    # 需求已由销售在需求卡片上确认（跨轮次保留；功能 / 端变了会回到待确认）
    requirement_confirmed: NotRequired[bool]
    confirmed_requirement: NotRequired[dict[str, Any] | None]  # 本轮从需求卡片提交的确认结果
    clarify: NotRequired[dict[str, Any] | None]  # 需求确认前的粗估（价格区间、问题）
    missing: NotRequired[list[str]]
    tiers: NotRequired[list[dict[str, Any]]]
    margin_ok: NotRequired[bool]
    margin_reason: NotRequired[str]
    retry: NotRequired[int]
    hint: NotRequired[str | None]
    chosen_tier: NotRequired[str | None]  # 确认生成报价时销售另选的档位（tier 键），None 按推荐档
    # 确认时在方案卡上调整的数量（sku → 数量，0 为删除）；None 按原方案
    adjusted_qty: NotRequired[dict[str, int] | None]
    decision: NotRequired[str | None]
    quote: NotRequired[dict[str, Any] | None]
    tool_log: NotRequired[list[dict[str, Any]]]  # 本轮工具结果摘要，respond 用
    error: NotRequired[dict[str, Any] | None]
    # function calling 循环（tool_agent）
    scratch: NotRequired[list[AnyMessage]]  # 本轮与模型的工作消息（含 tool_calls 和工具结果）
    pending_call: NotRequired[dict[str, Any] | None]  # 等待确认的写操作 {id, name, args, preview}
    tool_rounds: NotRequired[int]
    agent_reply: NotRequired[str | None]  # 模型在循环里已经流式输出的回复，respond 不再重复生成
    # 确认后写操作的执行结果 {action, status: done/failed/cancelled, summary, href}
    action_result: NotRequired[dict[str, Any] | None]


def turn_reset() -> dict[str, Any]:
    """每轮开始时清空的字段（requirement 保留，用于多轮补充需求）。"""
    return {
        "intent": "chitchat",
        "solution_request": None,
        "missing": [],
        "tiers": [],
        "clarify": None,
        "margin_ok": False,
        "margin_reason": "",
        "retry": 0,
        "hint": None,
        "decision": None,
        "quote": None,
        "tool_log": [],
        "error": None,
        "scratch": [],
        "pending_call": None,
        "tool_rounds": 0,
        "agent_reply": None,
        "action_result": None,
    }
