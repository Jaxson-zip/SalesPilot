"""路由：别名 / 分组 → 按顺序调用，失败切换（差异 #12 #14）。

- 每个候选模型先按自己的能力表做请求规范化，再交给 Backend（litellm.Router）调用；
- 非流式：失败就切到分组里的下一个；
- 流式：拿到上游第一片之前失败可以切换；之后失败只发 error 事件，不再切换（#14）；
- 需要伪流式（#11）的模型走非流式调用再切片。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from app.backend import Backend, to_dict
from app.compat.errors import (
    GatewayError,
    aggregate_errors,
    capability_mismatch,
    classify_exception,
    error_body,
    should_failover,
)
from app.compat.request import normalize_request, wants_json
from app.compat.response import (
    ensure_json_content,
    normalize_embedding,
    normalize_rerank,
    normalize_response,
)
from app.compat.stream import (
    SSE_DONE,
    StreamState,
    estimate_prompt_tokens,
    finalize,
    normalize_usage,
    process_chunk,
    pseudo_stream,
    sse_encode,
)
from app.logging import CallLog
from app.registry import ModelEntry, Registry


def _completion_text(resp: dict[str, Any]) -> str:
    msg = ((resp.get("choices") or [{}])[0]).get("message") or {}
    return (msg.get("content") or "") + str(msg.get("tool_calls") or "")


def needs_pseudo_stream(entry: ModelEntry, body: dict[str, Any]) -> bool:
    caps = entry.capabilities
    return not caps.stream or (bool(body.get("tools")) and not caps.stream_tools)


async def _iter_list(items: list[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


class GatewayRouter:
    def __init__(self, registry: Registry, backend: Backend) -> None:
        self.registry = registry
        self.backend = backend
        self.health: dict[str, dict[str, Any]] = {}

    # ---------- 公共 ----------

    def _resolve_chat(self, body: dict[str, Any]) -> list[ModelEntry]:
        name = str(body.get("model") or "")
        needs_tools = bool(body.get("tools"))
        entries = self.registry.resolve(name, needs_tools=needs_tools)
        if entries:
            return entries
        if needs_tools and self.registry.resolve(name):
            raise capability_mismatch(f"No model in group '{name}' supports tool calls")
        raise GatewayError(
            502,
            50201,
            f"No available model in group '{name}' (check API keys)",
            "api_error",
            "no_available_model",
        )

    def _mark(self, alias: str, err: GatewayError | None) -> None:
        self.health[alias] = {
            "ok": err is None,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "error": None if err is None else err.code,
        }

    def _record_failure(
        self, entry: ModelEntry, exc: BaseException, attempts: list[tuple[str, GatewayError]], log: CallLog
    ) -> bool:
        """记录一次失败；返回是否继续切换到下一个模型。"""
        err = classify_exception(exc)
        attempts.append((entry.alias, err))
        log.attempts.append({"model": entry.alias, "status": err.status, "code": err.code})
        self._mark(entry.alias, err)
        return should_failover(err)

    def _success(self, entry: ModelEntry, attempts: list[Any], log: CallLog) -> None:
        self._mark(entry.alias, None)
        log.actual_model = entry.alias
        log.fallback = bool(attempts)

    # ---------- 非流式 ----------

    async def _complete_one(self, entry: ModelEntry, body: dict[str, Any], log: CallLog) -> dict[str, Any]:
        req, downgrades = normalize_request(body, entry.capabilities)
        log.downgrades = downgrades
        req.pop("model", None)
        req.pop("stream_options", None)
        req["stream"] = False
        raw = await self.backend.chat(entry.alias, req)
        resp, fixes = normalize_response(to_dict(raw), entry.alias)
        if wants_json(body):
            resp, json_fixes = ensure_json_content(resp)
            fixes += json_fixes
        prompt_tokens = estimate_prompt_tokens(req["messages"])
        resp["usage"] = normalize_usage(resp.get("usage"), prompt_tokens, _completion_text(resp))
        log.fixes = fixes
        log.usage = resp["usage"]
        return resp

    async def complete(self, body: dict[str, Any], log: CallLog) -> dict[str, Any]:
        entries = self._resolve_chat(body)
        attempts: list[tuple[str, GatewayError]] = []
        for entry in entries:
            try:
                resp = await self._complete_one(entry, body, log)
            except Exception as exc:  # noqa: BLE001 - 任何上游异常都要归类
                if not self._record_failure(entry, exc, attempts, log):
                    break
                continue
            self._success(entry, attempts, log)
            return resp
        raise aggregate_errors(attempts, self.registry.is_group(str(body.get("model"))))

    # ---------- 流式 ----------

    async def _start_stream(
        self, entry: ModelEntry, body: dict[str, Any], log: CallLog
    ) -> AsyncIterator[str]:
        """拿到上游第一片后返回输出迭代器；在此之前的异常向上抛，由调用方切换模型。"""
        if needs_pseudo_stream(entry, body):
            resp = await self._complete_one(entry, body, log)
            log.pseudo_stream = True
            prompt_tokens = int(resp["usage"]["prompt_tokens"])
            chunks = [sse_encode(c) for c in pseudo_stream(resp, prompt_tokens)]
            return _iter_list([*chunks, SSE_DONE])
        req, downgrades = normalize_request(body, entry.capabilities)
        log.downgrades = downgrades
        req.pop("model", None)
        req["stream"] = True
        if entry.capabilities.stream_usage:
            req["stream_options"] = {"include_usage": True}
        else:
            req.pop("stream_options", None)
        upstream = await self.backend.chat(entry.alias, req)
        if isinstance(upstream, dict):  # 上游忽略了 stream，按伪流式处理
            resp, _ = normalize_response(upstream, entry.alias)
            chunks = [sse_encode(c) for c in pseudo_stream(resp, estimate_prompt_tokens(req["messages"]))]
            return _iter_list([*chunks, SSE_DONE])
        iterator = aiter(upstream)
        first = await anext(iterator, None)
        state = StreamState(model=entry.alias)
        return self._relay(state, first, iterator, estimate_prompt_tokens(req["messages"]), log)

    async def _relay(
        self,
        state: StreamState,
        first: dict[str, Any] | None,
        iterator: AsyncIterator[dict[str, Any]],
        prompt_tokens: int,
        log: CallLog,
    ) -> AsyncIterator[str]:
        """首字节之后：逐片规范化输出；中途失败发送 error 事件，不切换（#14）。"""
        try:
            if first is not None:
                for chunk in process_chunk(state, to_dict(first)):
                    yield sse_encode(chunk)
            async for raw in iterator:
                for chunk in process_chunk(state, to_dict(raw)):
                    yield sse_encode(chunk)
            final = finalize(state, prompt_tokens)
            log.usage = final[-1].get("usage")
            for chunk in final:
                yield sse_encode(chunk)
            yield SSE_DONE
        except Exception as exc:  # noqa: BLE001
            err = classify_exception(exc)
            log.status, log.error_code = "error", err.code
            if log.actual_model:
                self._mark(log.actual_model, err)
            yield sse_encode(error_body(err))
        finally:
            log.fixes += state.fixes

    async def open_stream(self, body: dict[str, Any], log: CallLog) -> AsyncIterator[str]:
        """返回 SSE 文本迭代器；所有候选在首字节前都失败时抛 GatewayError（此时还能返回普通 HTTP 错误）。"""
        entries = self._resolve_chat(body)
        attempts: list[tuple[str, GatewayError]] = []
        for entry in entries:
            try:
                stream = await self._start_stream(entry, body, log)
            except Exception as exc:  # noqa: BLE001
                if not self._record_failure(entry, exc, attempts, log):
                    break
                continue
            self._success(entry, attempts, log)
            return stream
        raise aggregate_errors(attempts, self.registry.is_group(str(body.get("model"))))

    # ---------- Embedding ----------

    async def embed(self, body: dict[str, Any], log: CallLog) -> dict[str, Any]:
        name = str(body.get("model") or "")
        entries = self.registry.resolve(name, kind="embedding")
        params = {k: v for k, v in body.items() if k in ("input", "dimensions", "encoding_format", "user")}
        attempts: list[tuple[str, GatewayError]] = []
        for entry in entries:
            try:
                raw = await self.backend.embed(entry.alias, params)
            except Exception as exc:  # noqa: BLE001
                if not self._record_failure(entry, exc, attempts, log):
                    break
                continue
            self._success(entry, attempts, log)
            resp = normalize_embedding(to_dict(raw), entry.alias)
            log.usage = resp["usage"]
            return resp
        raise aggregate_errors(attempts, self.registry.is_group(name))

    # ---------- 重排 ----------

    async def rerank(self, body: dict[str, Any], log: CallLog) -> dict[str, Any]:
        """分组内可以失败切换：重排分数只用于本次排序，不像向量那样要求前后一致。"""
        name = str(body.get("model") or "")
        entries = self.registry.resolve(name, kind="rerank")
        documents = list(body.get("documents") or [])
        params: dict[str, Any] = {"query": body["query"], "documents": documents}
        if body.get("top_n"):
            params["top_n"] = body["top_n"]
        attempts: list[tuple[str, GatewayError]] = []
        for entry in entries:
            try:
                raw = await self.backend.rerank(entry.alias, params)
            except Exception as exc:  # noqa: BLE001
                if not self._record_failure(entry, exc, attempts, log):
                    break
                continue
            self._success(entry, attempts, log)
            return normalize_rerank(to_dict(raw), entry.alias, len(documents))
        raise aggregate_errors(attempts, self.registry.is_group(name))
