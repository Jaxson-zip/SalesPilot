"""唯一的大模型调用入口：所有 chat / embeddings / 模型列表请求都经网关（OpenAI 兼容）。

- 只把 langchain-openai 的 ChatOpenAI 当作 OpenAI 客户端使用，base_url 指向网关；
- model 填网关的别名或分组名（默认 LLM_DEFAULT_GROUP，例如 chat-agent）；
- 每次调用透传当前请求的 X-Request-ID；
- core 其他代码禁止自行创建模型客户端。
"""

import logging
import time
from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode
from app.common.request_id import REQUEST_ID_HEADER, get_request_id
from app.llm.usage import UsageCallback

logger = logging.getLogger("core.llm")


def _headers(request_id: str | None = None) -> dict[str, str]:
    rid = request_id or get_request_id()
    return {REQUEST_ID_HEADER: rid} if rid else {}


def get_chat_model(
    model: str | None = None,
    *,
    temperature: float = 0.2,
    streaming: bool = True,
    request_id: str | None = None,
) -> BaseChatModel:
    """返回指向网关的聊天模型。model 为空时用默认分组。"""
    settings = get_settings()
    return ChatOpenAI(
        base_url=settings.llm_gateway_base,
        api_key=settings.llm_gateway_key,  # type: ignore[arg-type]
        model=model or settings.llm_default_group,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,  # 重试和失败切换由网关负责
        streaming=streaming,
        stream_usage=True,  # 流式也拿到 token 用量（网关在最后一片返回 usage）
        default_headers=_headers(request_id),
        callbacks=[
            UsageCallback(model or settings.llm_default_group, request_id or get_request_id())
        ],
    )


def _map_http_error(exc: httpx.HTTPError) -> BizError:
    if isinstance(exc, httpx.TimeoutException):
        return BizError(ErrorCode.TIMEOUT)
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return BizError(ErrorCode.RATE_LIMITED)
    return BizError(ErrorCode.UPSTREAM, f"模型网关上游错误：{exc}")


def map_llm_error(exc: Exception) -> BizError:
    """把 OpenAI 客户端异常映射为 §8.2 错误码（按类名判断，避免在 core 里依赖厂商 SDK 类型）。"""
    if isinstance(exc, BizError):
        return exc
    if isinstance(exc, httpx.HTTPError):
        return _map_http_error(exc)
    name = type(exc).__name__
    if "Timeout" in name:
        return BizError(ErrorCode.TIMEOUT)
    if "RateLimit" in name:
        return BizError(ErrorCode.RATE_LIMITED)
    if name in {"APIError", "APIConnectionError", "APIStatusError", "InternalServerError"}:
        return BizError(ErrorCode.UPSTREAM)
    return BizError(ErrorCode.INTERNAL)


def _client(request_id: str | None = None) -> httpx.Client:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.llm_gateway_key}", **_headers(request_id)}
    return httpx.Client(
        base_url=settings.llm_gateway_base, headers=headers, timeout=settings.llm_timeout_seconds
    )


def embed_texts(
    texts: list[str], *, model: str | None = None, request_id: str | None = None
) -> list[list[float]]:
    """调用网关 /embeddings，返回与输入等长的向量列表。"""
    if not texts:
        return []
    payload = {"model": model or get_settings().llm_embed_group, "input": texts}
    try:
        with _client(request_id) as client:
            resp = client.post("/embeddings", json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _map_http_error(exc) from exc
    items = sorted(resp.json()["data"], key=lambda d: d["index"])
    return [item["embedding"] for item in items]


def rerank_texts(
    query: str,
    documents: list[str],
    *,
    top_n: int | None = None,
    model: str | None = None,
    request_id: str | None = None,
) -> list[tuple[int, float]]:
    """调用网关 /rerank，返回 [(原下标, 相关度)]，按相关度从高到低。"""
    payload: dict[str, Any] = {
        "model": model or get_settings().llm_rerank_group,
        "query": query,
        "documents": documents,
    }
    if top_n:
        payload["top_n"] = top_n
    try:
        with _client(request_id) as client:
            resp = client.post("/rerank", json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _map_http_error(exc) from exc
    return [(int(r["index"]), float(r["relevance_score"])) for r in resp.json()["results"]]


def list_models(request_id: str | None = None) -> list[dict[str, Any]]:
    """读取网关 /models（别名、分组、能力表）。"""
    try:
        with _client(request_id) as client:
            resp = client.get("/models")
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _map_http_error(exc) from exc
    data = resp.json().get("data", [])
    return data if isinstance(data, list) else []


def gateway_admin(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """网关管理接口 /v1/admin/*：厂商 Key 的状态、推送和测试连接（只给 model_keys_service 用）。"""
    try:
        with _client() as client:
            resp = client.request(method, f"/admin/{path}", json=body)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _map_http_error(exc) from exc
    data = resp.json()
    return data if isinstance(data, dict) else {}


def forget_availability() -> None:
    """换了 Key：下次按网关的最新状态判断模型是否可用。"""
    _AVAILABILITY.clear()


# 模型可用性缓存：{别名或分组: (是否可用, 查询时间)}
_AVAILABILITY: dict[str, tuple[bool, float]] = {}
AVAILABILITY_TTL_SECONDS = 30.0


def model_available(name: str | None = None, request_id: str | None = None) -> bool:
    """网关里这个别名 / 分组是否有可用的模型（配了 Key）。

    没有可用模型时 Agent 直接走规则兜底，不必每个节点都去调一次必然失败的接口。
    结果缓存 30 秒；网关不可达时视为不可用。
    """
    target = name or get_settings().llm_default_group
    cached = _AVAILABILITY.get(target)
    now = time.monotonic()
    if cached and now - cached[1] < AVAILABILITY_TTL_SECONDS:
        return cached[0]
    try:
        cards = list_models(request_id)
    except BizError:
        logger.warning("gateway unreachable, agent uses rule fallback")
        cards = []
    available = any(c.get("id") == target and c.get("available") for c in cards)
    _AVAILABILITY[target] = (available, now)
    return available
