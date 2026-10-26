"""按剧本回复的假聊天模型：测试 function calling 循环，不依赖网关和真实 Key（AGENTS 第 16 条）。

每次调用（invoke / stream / with_structured_output）按顺序取剧本里的下一条 AIMessage；
带 tool_calls 的消息在流式输出时拆成 tool_call_chunks，和真实模型的流式工具调用一致。
"""

import json
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field


def call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    """一条只包含一个工具调用的模型回复。"""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


class ScriptedModel(BaseChatModel):
    script: list[AIMessage]
    seen: list[list[BaseMessage]] = Field(default_factory=list)  # 每次调用收到的消息
    bound: list[list[str]] = Field(default_factory=list)  # 每次 bind_tools 绑定的工具名
    fail: bool = False  # True 时每次调用都抛异常，模拟网关不可用

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedModel":
        names = [t["function"]["name"] if isinstance(t, dict) else str(t) for t in tools]
        self.bound.append(names)
        return self

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        if self.fail:
            raise ConnectionError("gateway down")
        self.seen.append(list(messages))
        if not self.script:
            raise AssertionError("剧本已用完：模型被多调用了一次")
        return self.script.pop(0)

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kw: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _stream(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kw: Any
    ) -> Iterator[ChatGenerationChunk]:
        msg = self._next(messages)
        text = msg.content if isinstance(msg.content, str) else ""
        for i in range(0, len(text), 4):  # 正文分片，验证 message.delta 是流式的
            yield ChatGenerationChunk(message=AIMessageChunk(content=text[i : i + 4]))
        if msg.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": i}
                for i, c in enumerate(msg.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks))
