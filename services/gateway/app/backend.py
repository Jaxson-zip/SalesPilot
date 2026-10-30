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

    async def probe(self, entry: ModelEntry) -> None:
        """用 entry 里的 Key 发一次最小请求（测试连接）；失败时抛出上游异常。"""
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

    async def probe(self, entry: ModelEntry) -> None:
        self._get_router()  # 确保 litellm 已按上面的设置初始化
        import litellm

        params: dict[str, Any] = {"model": entry.litellm_model, "api_key": entry.api_key, "timeout": 20}
        if entry.api_base:
            params["api_base"] = entry.api_base
        if entry.is_embedding:
            await litellm.aembedding(input=["ping"], **params)
        else:
            await litellm.acompletion(messages=[{"role": "user", "content": "ping"}], max_tokens=1, **params)
