"""对话可选的模型：从网关能力表里挑出支持工具调用的模型 / 分组，并标出是否已配置可用。

前端模型选择器据此显示「未配置」，全部不可用时提示当前为规则模式（不调用大模型）。
"""

from typing import Any, Literal

from pydantic import BaseModel

from app.common.config import get_settings
from app.common.errors import BizError
from app.llm.client import list_models


class ChatModelOut(BaseModel):
    id: str
    type: Literal["model", "group"]
    available: bool
    members: list[str] = []


class ChatModels(BaseModel):
    items: list[ChatModelOut]
    default: str
    any_available: bool
    gateway_ok: bool


def _usable_for_agent(card: dict[str, Any]) -> bool:
    caps = card.get("capabilities") or {}
    return bool(caps.get("tools")) and not caps.get("embeddings")


def chat_models(request_id: str | None = None) -> ChatModels:
    """网关不可达时不报错：返回空列表并标记 gateway_ok=false，对话仍可用规则模式。"""
    try:
        cards = list_models(request_id)
        gateway_ok = True
    except BizError:
        cards, gateway_ok = [], False
    items = [
        ChatModelOut(
            id=str(c["id"]),
            type="group" if c.get("type") == "group" else "model",
            available=bool(c.get("available")),
            members=list(c.get("members") or []),
        )
        for c in cards
        if _usable_for_agent(c)
    ]
    return ChatModels(
        items=items,
        default=get_settings().llm_default_group,
        any_available=any(i.available for i in items),
        gateway_ok=gateway_ok,
    )
