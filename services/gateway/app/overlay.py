"""网页上的模型配置：core 推过来，叠加在 models.yaml + .env 之上，立即生效（不用重启）。

- 内置厂商（models.yaml 里 api_key 写成 ${VAR} 的一组模型）：可以改 Key、接口地址、协议；
- 自定义厂商：网页上新增的 OpenAI 兼容 / LiteLLM 原生接口，模型别名为「厂商 id-模型名」；
- 默认模型：chat-agent / embed / rerank 三个分组的成员和顺序；
- 每次推送都是完整配置，没带的回到 models.yaml / .env；只放在内存里，网关重启后由 core 按 version 补推；
- Key 不会出现在任何响应和日志里，测试连接的报错也会把 Key 替换掉。
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.backend import Backend
from app.compat.errors import classify_exception, invalid_param
from app.registry import (
    Capabilities,
    ModelEntry,
    ModelKind,
    Registry,
    expand_env,
    key_var,
    registry_from_data,
)

# 网页上能调整的分组 → 成员必须是哪类模型
EDITABLE_GROUPS: dict[str, ModelKind] = {"chat-agent": "chat", "embed": "embedding", "rerank": "rerank"}
_ID = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
_ADAPTER = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_SLUG = re.compile(r"[^a-z0-9.]+")
# 「litellm.BadRequestError: OpenAIException - 」这类前缀对管理员没有意义
_NOISE = re.compile(r"^(litellm\.\w+:\s*)?(\w+Error:\s*)?(\w+Exception\s*-\s*)?")
_UNREACHABLE = re.compile(r"Connection error|timed out|Timeout|Name or service not known", re.I)

LinkType = Literal["openai_compat", "native"]


class BuiltinOverride(BaseModel):
    """内置厂商的改写；空值 = 用 models.yaml / .env 的。"""

    key: str = Field(default="", max_length=500)
    base: str = Field(default="", max_length=500)
    protocol: Literal["", "openai_compat", "native"] = ""
    adapter: str = Field(default="", max_length=32)  # protocol=native 时的 LiteLLM 适配名，如 deepseek


class CustomModel(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    kind: ModelKind = "chat"
    capabilities: Capabilities = Field(default_factory=Capabilities)


class CustomProvider(BaseModel):
    id: str = Field(min_length=2, max_length=24)
    protocol: LinkType = "openai_compat"
    adapter: str = Field(default="", max_length=32)
    api_base: str = Field(default="", max_length=500)
    api_key: str = Field(default="", max_length=500)
    models: list[CustomModel] = Field(default_factory=list, max_length=20)


class ModelConfig(BaseModel):
    version: str = Field(default="", max_length=64)
    builtin: dict[str, BuiltinOverride] = Field(default_factory=dict)
    custom: list[CustomProvider] = Field(default_factory=list, max_length=20)
    groups: dict[str, list[str]] = Field(default_factory=dict)


class TestRequest(BaseModel):
    """测试连接：内置厂商带 var + 表单上的改写（key 空 = 当前生效的）；自定义厂商带只含一个模型的 provider"""

    var: str | None = Field(default=None, max_length=64)
    override: BuiltinOverride | None = None
    provider: CustomProvider | None = None
    detect: bool = False  # 对话模型：顺便检测工具调用 / 流式 / JSON 能力


def custom_alias(provider_id: str, model: str) -> str:
    return f"{provider_id}-{_SLUG.sub('-', model.lower()).strip('-')}"


def _model_name(protocol: str, adapter: str, bare: str) -> str:
    return f"{adapter}/{bare}" if protocol == "native" else bare


def _bare(item: Mapping[str, Any]) -> str:
    model = str(item["model"])
    return model.split("/", 1)[1] if item.get("link") == "native" and "/" in model else model


def _check_base(url: str, field: str) -> None:
    if url and not re.match(r"^https?://[^\s/]+", url):
        raise invalid_param("api base must be an http(s) URL", field)


def _check_protocol(protocol: str, adapter: str, field: str) -> None:
    if protocol == "native" and not _ADAPTER.match(adapter):
        raise invalid_param("native protocol needs a LiteLLM adapter name", field)


def validate(cfg: ModelConfig, source: Mapping[str, Any]) -> None:
    builtin_aliases = {str(m["alias"]) for m in source.get("models") or []}
    known_vars = {key_var(m) for m in source.get("models") or []} - {None}
    unknown = sorted(set(cfg.builtin) - known_vars)
    if unknown:
        raise invalid_param(f"unknown key variables: {unknown}", "builtin")
    for var, ov in cfg.builtin.items():
        _check_base(ov.base, f"builtin.{var}.base")
        if ov.protocol:
            _check_protocol(ov.protocol, ov.adapter, f"builtin.{var}.adapter")
    taken = builtin_aliases | set(source.get("groups") or {})
    ids: set[str] = set()
    for p in cfg.custom:
        if not _ID.match(p.id) or p.id in ids:
            raise invalid_param(f"invalid or duplicate provider id: {p.id}", "custom.id")
        ids.add(p.id)
        _check_base(p.api_base, f"custom.{p.id}.api_base")
        _check_protocol(p.protocol, p.adapter, f"custom.{p.id}.adapter")
        for m in p.models:
            alias = custom_alias(p.id, m.model)
            if alias in taken:
                raise invalid_param(f"duplicate model alias: {alias}", f"custom.{p.id}.models")
            taken.add(alias)
    extra = sorted(set(cfg.groups) - set(EDITABLE_GROUPS))
    if extra:
        raise invalid_param(f"groups not editable: {extra}", "groups")


def _apply_builtin(item: dict[str, Any], ov: BuiltinOverride) -> None:
    if ov.key.strip():
        item["api_key"] = ov.key.strip()
    if ov.base.strip():
        item["api_base"] = ov.base.strip()
    rerank = bool((item.get("capabilities") or {}).get("rerank"))
    if ov.protocol and not rerank:  # 重排不是 OpenAI 标准接口，只能走原生适配，不跟着改
        item["model"] = _model_name(ov.protocol, ov.adapter, _bare(item))
        item["link"] = ov.protocol


def _custom_items(p: CustomProvider) -> list[dict[str, Any]]:
    items = []
    for m in p.models:
        caps = m.capabilities.model_copy(
            update={
                "embeddings": m.kind == "embedding",
                "rerank": m.kind == "rerank",
                "stream": m.capabilities.stream and m.kind == "chat",
            }
        )
        items.append(
            {
                "alias": custom_alias(p.id, m.model),
                "link": p.protocol,
                "model": _model_name(p.protocol, p.adapter, m.model),
                "api_base": p.api_base.strip(),
                "api_key": p.api_key.strip(),
                "capabilities": caps.model_dump(),
                "origin": "custom",
                "provider": p.id,
            }
        )
    return items


def _fits(entry: ModelEntry, kind: ModelKind) -> bool:
    if entry.kind != kind:
        return False
    return kind != "chat" or entry.capabilities.tools  # chat-agent 只放能调用工具的


def build_registry(source: Mapping[str, Any], env: Mapping[str, str], cfg: ModelConfig) -> Registry:
    data = expand_env(copy.deepcopy(dict(source)), env)
    items: list[dict[str, Any]] = list(data.get("models") or [])
    for raw_item, item in zip(source.get("models") or [], items, strict=True):
        var = key_var(raw_item)
        item["provider"] = var or ""
        if var and var in cfg.builtin:
            _apply_builtin(item, cfg.builtin[var])
    for p in cfg.custom:
        items += _custom_items(p)
    data["models"] = items
    registry = registry_from_data(data, source)
    for name, kind in EDITABLE_GROUPS.items():
        members = [
            a for a in cfg.groups.get(name, []) if a in registry.models and _fits(registry.models[a], kind)
        ]
        if kind == "embedding":
            members = members[:1]  # 不同模型的向量不能互相比较，向量分组只放一个
        if members:  # 选的模型都被删掉了：回到 models.yaml 的默认
            registry.groups[name] = members
    return registry


def _card(entry: ModelEntry) -> dict[str, Any]:
    return {
        "alias": entry.alias,
        "model": entry.model,
        "link": entry.link,
        "kind": entry.kind,
        "tools": entry.capabilities.tools,
        "dims": entry.capabilities.dims,
        "available": entry.available,
        "unavailable_reason": entry.unavailable_reason,
    }


class OverlayManager:
    def __init__(self, registry: Registry, backend: Backend, env: Mapping[str, str]) -> None:
        self.registry = registry
        self.backend = backend
        self.base_env = dict(env)
        self.config = ModelConfig()  # version 为空 = 还没收到过 core 的配置

    def _build(self, cfg: ModelConfig) -> Registry:
        return build_registry(self.registry.source, self.base_env, cfg)

    def apply(self, cfg: ModelConfig) -> None:
        validate(cfg, self.registry.source)
        try:
            fresh = self._build(cfg)
        except ValueError as exc:
            raise invalid_param(str(exc), "custom") from exc
        self.registry.replace_with(fresh)
        self.backend.reset()
        self.config = cfg

    def state(self) -> dict[str, Any]:
        defaults = self._build(ModelConfig())
        builtin = []
        for var, aliases in self.registry.key_vars().items():
            ov = self.config.builtin.get(var, BuiltinOverride())
            models = [self.registry.models[a] for a in aliases]
            default_base = next(
                (defaults.models[a].api_base for a in aliases if defaults.models[a].api_base), ""
            )
            builtin.append(
                {
                    "var": var,
                    "env_configured": bool(self.base_env.get(var, "").strip()),
                    "key_overridden": bool(ov.key.strip()),
                    "base": ov.base,
                    "default_base": default_base,
                    "protocol": ov.protocol,
                    "adapter": ov.adapter,
                    "available": any(m.available for m in models),
                    "models": [_card(m) for m in models],
                }
            )
        custom = []
        for p in self.config.custom:
            models = [self.registry.models[custom_alias(p.id, m.model)] for m in p.models]
            custom.append(
                {
                    "id": p.id,
                    "available": any(m.available for m in models),
                    "models": [_card(m) for m in models],
                }
            )
        return {
            "version": self.config.version,
            "builtin": builtin,
            "custom": custom,
            "groups": {g: list(self.registry.groups.get(g, [])) for g in EDITABLE_GROUPS},
            "group_defaults": {g: list(defaults.groups.get(g, [])) for g in EDITABLE_GROUPS},
        }

    def _test_entry(self, body: TestRequest) -> ModelEntry:
        cfg = self.config.model_copy(deep=True)
        if body.provider is not None:
            if len(body.provider.models) != 1:
                raise invalid_param("test exactly one model", "provider.models")
            cfg.custom = [p for p in cfg.custom if p.id != body.provider.id] + [body.provider]
            alias = custom_alias(body.provider.id, body.provider.models[0].model)
        elif body.var:
            aliases = self.registry.key_vars().get(body.var)
            if not aliases:
                raise invalid_param(f"unknown key variable: {body.var}", "var")
            current = cfg.builtin.get(body.var, BuiltinOverride())
            override = body.override or current
            if not override.key.strip():  # 没填新 Key：测当前生效的（网页值或 .env）
                override = override.model_copy(update={"key": current.key})
            cfg.builtin[body.var] = override
            # 优先用对话模型测：最常用，且各家都支持
            entries = [self.registry.models[a] for a in aliases]
            alias = next((e for e in entries if e.is_chat), entries[0]).alias
        else:
            raise invalid_param("var or provider is required", "var")
        validate(cfg, self.registry.source)
        try:
            return self._build(cfg).models[alias]
        except ValueError as exc:
            raise invalid_param(str(exc), "provider") from exc

    async def test(self, body: TestRequest) -> dict[str, Any]:
        entry = self._test_entry(body)
        result: dict[str, Any] = {
            "ok": False,
            "model": entry.alias,
            "error": None,
            "dims": None,
            "capabilities": None,
        }
        key = entry.api_key.strip()
        if not key:
            return {**result, "error": "没有可用的 Key"}
        if not entry.api_base and entry.link == "openai_compat":
            return {**result, "error": "接口地址没有配置"}
        try:
            info = await self.backend.probe(entry)
        except Exception as exc:  # 把上游错误转成一句话，去掉可能回显的 Key
            message = _NOISE.sub("", classify_exception(exc).message.replace(key, "***"))
            if _UNREACHABLE.search(message):
                message = f"连不上这个地址，检查接口地址和服务器能否访问外网（{message}）"
            return {**result, "error": message[:300]}
        result.update(ok=True, dims=info.get("dims"))
        if body.detect and entry.is_chat:
            result["capabilities"] = await self.backend.detect(entry)
        return result
