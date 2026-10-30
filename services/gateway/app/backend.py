"""上游调用后端：用 litellm.Router 做各家协议转换和同模型重试。

分组内的失败切换由 app/router.py 自己做（每个模型的请求要按各自能力表规范化，
且只能在首字节之前切换），所以这里每个别名只注册一个 deployment。
测试里用实现了同样接口的 Fake 后端替换，不访问外网。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.registry import ModelEntry, Registry

ChatResult = dict[str, Any] | AsyncIterator[dict[str, Any]]


class Backend(Protocol):
    async def chat(self, alias: str, params: dict[str, Any]) -> ChatResult:
        """params["stream"] 为 True 时返回分片异步迭代器，否则返回完整响应 dict。"""
        ...

    async def embed(self, alias: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def rerank(self, alias: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def probe(self, entry: ModelEntry) -> dict[str, Any]:
        """用 entry 里的 Key 发一次最小请求（测试连接），失败时抛出上游异常；Embedding 返回 {"dims": n}。"""
        ...

    async def detect(self, entry: ModelEntry) -> dict[str, bool]:
        """对话模型的能力检测：工具调用、流式、流式工具调用、JSON 模式。单项失败记为 False。"""
        ...

    def reset(self) -> None:
        """注册表换了 Key：下次调用按新的注册表重建。"""
        ...


def to_dict(obj: Any) -> dict[str, Any]:
    """把 LiteLLM 的 ModelResponse / 分片对象转成普通 dict。"""
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        result = dump()
        if isinstance(result, dict):
            return result
    return dict(obj)


def build_model_list(registry: Registry, timeout: float) -> list[dict[str, Any]]:
    """注册表 → litellm.Router 的 model_list（只包含可用模型）。"""
    model_list: list[dict[str, Any]] = []
    for entry in registry.models.values():
        if not entry.available:
            continue
        params: dict[str, Any] = {"model": entry.litellm_model, "api_key": entry.api_key, "timeout": timeout}
        if entry.api_base:
            params["api_base"] = entry.api_base
        model_list.append({"model_name": entry.alias, "litellm_params": params})
    return model_list


async def _iter_dicts(stream: Any) -> AsyncIterator[dict[str, Any]]:
    async for chunk in stream:
        yield to_dict(chunk)


class LiteLLMBackend:
    """首次调用时才 import litellm 并构造 Router，保证服务启动快、测试不依赖它。"""

    def __init__(self, registry: Registry, timeout: float) -> None:
        self._registry = registry
        self._timeout = timeout
        self._router: Any = None

    def _get_router(self) -> Any:
        if self._router is None:
            os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # 不在启动时联网拉价格表
            import litellm

            litellm.telemetry = False
            litellm.suppress_debug_info = True
            self._router = litellm.Router(
                model_list=build_model_list(self._registry, self._timeout),
                num_retries=self._registry.settings.retries,
                timeout=self._timeout,
            )
        return self._router

    async def chat(self, alias: str, params: dict[str, Any]) -> ChatResult:
        resp = await self._get_router().acompletion(model=alias, **params)
        if params.get("stream"):
            return _iter_dicts(resp)
        return to_dict(resp)

    async def rerank(self, alias: str, params: dict[str, Any]) -> dict[str, Any]:
        return to_dict(await self._get_router().arerank(model=alias, **params))

    async def embed(self, alias: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = await self._get_router().aembedding(model=alias, **params)
        return to_dict(resp)

    def reset(self) -> None:
        self._router = None

    def _probe_params(self, entry: ModelEntry) -> dict[str, Any]:
        self._get_router()  # 确保 litellm 已按上面的设置初始化
        params: dict[str, Any] = {"model": entry.litellm_model, "api_key": entry.api_key, "timeout": 20}
        if entry.api_base:
            params["api_base"] = entry.api_base
        return params

    async def probe(self, entry: ModelEntry) -> dict[str, Any]:
        import litellm

        params = self._probe_params(entry)
        if entry.is_embedding:
            resp = to_dict(await litellm.aembedding(input=["ping"], **params))
            return {"dims": len(resp["data"][0]["embedding"])}
        if entry.kind == "rerank":
            await litellm.arerank(query="ping", documents=["ping", "pong"], **params)
            return {}
        await litellm.acompletion(messages=[{"role": "user", "content": "ping"}], max_tokens=1, **params)
        return {}

    async def detect(self, entry: ModelEntry) -> dict[str, bool]:
        import litellm

        params = self._probe_params(entry)
        ask = [{"role": "user", "content": "现在几点？请调用 get_time 工具查询。"}]
        tool = {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "查询当前时间",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }

        async def tools() -> bool:
            resp = to_dict(await litellm.acompletion(messages=ask, tools=[tool], max_tokens=64, **params))
            return bool(((resp.get("choices") or [{}])[0].get("message") or {}).get("tool_calls"))

        async def stream(with_tools: bool) -> bool:
            extra: dict[str, Any] = {"tools": [tool]} if with_tools else {}
            messages = ask if with_tools else [{"role": "user", "content": "ping"}]
            resp = await litellm.acompletion(messages=messages, stream=True, max_tokens=64, **extra, **params)
            seen = False
            async for chunk in resp:
                delta = ((to_dict(chunk).get("choices") or [{}])[0].get("delta")) or {}
                seen = seen or bool(delta.get("tool_calls")) or not with_tools
            return seen

        async def json_mode() -> bool:
            await litellm.acompletion(
                messages=[{"role": "user", "content": '只回复 JSON：{"ok": true}'}],
                response_format={"type": "json_object"},
                max_tokens=16,
                **params,
            )
            return True

        async def safe(check: Any) -> bool:
            try:
                return bool(await check)
            except Exception:
                return False

        has_tools = await safe(tools())
        has_stream = await safe(stream(False))
        return {
            "tools": has_tools,
            "stream": has_stream,
            "stream_tools": has_tools and has_stream and await safe(stream(True)),
            "json_mode": await safe(json_mode()),
        }
