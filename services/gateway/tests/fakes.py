"""测试替身：Fake 后端、上游异常、样本加载。全部离线。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.registry import Registry, parse_registry

FIXTURES = Path(__file__).parent / "fixtures"
TEST_ENV = {"K_A": "key-a", "K_B": "key-b", "BASE": "http://upstream.invalid/v1"}


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / "synthetic" / name).read_text(encoding="utf-8"))


def upstream_error(name: str, status: int | None, message: str = "boom") -> Exception:
    """构造一个类名 / status_code 与 LiteLLM 异常相同的假异常。"""
    cls = type(name, (Exception,), {})
    exc = cls(message)
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


@dataclass
class StreamScript:
    chunks: list[dict[str, Any]]
    error_after: Exception | None = None

    async def iterate(self) -> AsyncIterator[dict[str, Any]]:
        for chunk in self.chunks:
            yield chunk
        if self.error_after is not None:
            raise self.error_after


@dataclass
class FakeBackend:
    """按别名预设返回：dict（非流式）、StreamScript（流式）或异常；列表依次消费。"""

    script: dict[str, list[Any]]
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def _next(self, alias: str) -> Any:
        items = self.script[alias]
        return items.pop(0) if len(items) > 1 else items[0]

    async def chat(self, alias: str, params: dict[str, Any]) -> Any:
        self.calls.append((alias, params))
        item = self._next(alias)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, StreamScript):
            return item.iterate()
        return item

    async def rerank(self, alias: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self.embed(alias, params)

    async def embed(self, alias: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((alias, params))
        item = self._next(alias)
        if isinstance(item, BaseException):
            raise item
        return item


def make_registry() -> Registry:
    raw = {
        "models": [
            {
                "alias": "m-tools",
                "model": "x",
                "api_base": "${BASE}",
                "api_key": "${K_A}",
                "capabilities": {"tools": True, "stream_tools": True, "tool_choice_required": True},
            },
            {
                "alias": "m-pseudo",
                "model": "y",
                "api_base": "${BASE}",
                "api_key": "${K_B}",
                "capabilities": {"tools": True, "stream_tools": False},
            },
            {
                "alias": "m-plain",
                "model": "z",
                "api_base": "${BASE}",
                "api_key": "${K_A}",
                "capabilities": {"tools": False},
            },
            {
                "alias": "m-nokey",
                "model": "w",
                "api_base": "${BASE}",
                "api_key": "${MISSING}",
                "capabilities": {"tools": True, "stream_tools": True},
            },
            {
                "alias": "m-embed",
                "model": "e",
                "api_base": "${BASE}",
                "api_key": "${K_A}",
                "capabilities": {"embeddings": True, "dims": 4},
            },
            {
                "alias": "m-rerank",
                "model": "r",
                "api_base": "${BASE}",
                "api_key": "${K_A}",
                "capabilities": {"rerank": True, "stream": False},
            },
            {
                "alias": "m-rerank-b",
                "model": "r2",
                "api_base": "${BASE}",
                "api_key": "${K_A}",
                "capabilities": {"rerank": True, "stream": False},
            },
        ],
        "groups": {
            "g-agent": ["m-nokey", "m-plain", "m-tools", "m-pseudo"],
            "g-chat": ["m-tools", "m-plain"],
            "embed": ["m-embed"],
            "rerank": ["m-rerank", "m-rerank-b"],
        },
    }
    return parse_registry(raw, TEST_ENV)


def text_response(content: str = "你好", model: str = "upstream") -> dict[str, Any]:
    return {
        "id": "resp-1",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    }


def parse_sse(text: str) -> list[Any]:
    """把 SSE 文本解析成 JSON 列表；[DONE] 原样保留为字符串。"""
    events: list[Any] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        data = block[len("data: ") :]
        events.append(data if data == "[DONE]" else json.loads(data))
    return events
