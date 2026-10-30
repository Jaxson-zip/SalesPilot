"""模型注册表：读取 models.yaml，展开 ${ENV}，能力查询，分组解析。

没有配置 Key（或地址）的模型标记为 unavailable：服务照常启动，分组里自动跳过。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.compat.errors import GatewayError, capability_mismatch, model_not_found

# ${VAR} 或 ${VAR:-默认值}（变量没设或为空时用默认值，与 shell 一致）
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


ModelKind = Literal["chat", "embedding", "rerank"]


class Capabilities(BaseModel):
    """模型能力表。未声明的能力按保守值处理，兼容层据此降级。"""

    model_config = ConfigDict(extra="allow")

    stream: bool = True
    tools: bool = False
    stream_tools: bool = False
    tool_choice_required: bool = False
    parallel_tool_calls: bool = False
    json_mode: bool = False
    json_schema: bool = False
    seed: bool = False
    stream_usage: bool = True
    simple_schema: bool = False  # true = 工具参数 schema 需要简化（去掉 anyOf/default 等）
    content_parts: bool = False  # true = 支持 content 为数组（多模态分段）
    max_tokens_param: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    temperature_max: float = 2.0
    max_output_tokens: int | None = None
    max_context: int | None = None
    embeddings: bool = False
    dims: int | None = None
    rerank: bool = False  # 重排模型（/v1/rerank）


class ModelEntry(BaseModel):
    alias: str
    link: Literal["openai_compat", "native"] = "openai_compat"
    model: str
    api_base: str = ""
    api_key: str = ""
    capabilities: Capabilities = Field(default_factory=Capabilities)
    available: bool = True
    unavailable_reason: str | None = None
    # builtin：models.yaml 里的；custom：管理员在网页上新增的。provider 为 Key 变量名或自定义厂商 id
    origin: Literal["builtin", "custom"] = "builtin"
    provider: str = ""

    @property
    def litellm_model(self) -> str:
        """openai_compat 走 LiteLLM 的 openai/ 适配；native 直接用 provider/model 写法。"""
        return f"openai/{self.model}" if self.link == "openai_compat" else self.model

    @property
    def kind(self) -> ModelKind:
        if self.capabilities.embeddings:
            return "embedding"
        return "rerank" if self.capabilities.rerank else "chat"

    @property
    def is_embedding(self) -> bool:
        return self.kind == "embedding"

    @property
    def is_chat(self) -> bool:
        return self.kind == "chat"


class RegistrySettings(BaseModel):
    timeout_seconds: float = 30
    retries: int = 1


class Registry(BaseModel):
    models: dict[str, ModelEntry]
    groups: dict[str, list[str]] = Field(default_factory=dict)
    settings: RegistrySettings = Field(default_factory=RegistrySettings)
    # 展开 ${ENV} 之前的 YAML：换 Key 时按新的变量值重新解析
    source: dict[str, Any] = Field(default_factory=dict, exclude=True)

    def key_vars(self) -> dict[str, list[str]]:
        """api_key 写成 ${VAR} 的变量 → 用它的模型别名（网页上可以填写的就是这些变量）。"""
        out: dict[str, list[str]] = {}
        for item in self.source.get("models") or []:
            var = key_var(item)
            if var:
                out.setdefault(var, []).append(str(item["alias"]))
        return out

    def replace_with(self, other: Registry) -> None:
        """原地替换内容：路由、后端都持有这个对象，换 Key 后不用重新组装应用。"""
        self.models, self.groups, self.settings = other.models, other.groups, other.settings

    def is_group(self, name: str) -> bool:
        return name in self.groups

    def groups_of(self, alias: str) -> list[str]:
        return [g for g, members in self.groups.items() if alias in members]

    def resolve(self, name: str, *, needs_tools: bool = False, kind: ModelKind = "chat") -> list[ModelEntry]:
        """别名 → [该模型]；分组 → 按顺序的可用成员（跳过不可用、能力不匹配的，差异 #12）。"""
        if name in self.groups:
            members = [self.models[a] for a in self.groups[name] if a in self.models]
            return [m for m in members if m.available and _fits(m, needs_tools, kind)]
        entry = self.models.get(name)
        if entry is None:
            raise model_not_found(name)
        if entry.kind != kind:
            raise capability_mismatch(f"Model '{name}' is a {entry.kind} model, not {kind}")
        if needs_tools and not entry.capabilities.tools:
            raise capability_mismatch(f"Model '{name}' does not support tool calls")
        if not entry.available:
            raise GatewayError(
                502,
                50201,
                f"Model '{name}' is unavailable: {entry.unavailable_reason}",
                "api_error",
                "model_unavailable",
            )
        return [entry]


def _fits(entry: ModelEntry, needs_tools: bool, kind: ModelKind) -> bool:
    if entry.kind != kind:
        return False
    return entry.capabilities.tools or not needs_tools


def key_var(item: Mapping[str, Any]) -> str | None:
    """api_key 恰好写成 ${VAR} 时返回变量名。"""
    hit = _ENV_PATTERN.fullmatch(str(item.get("api_key") or "").strip())
    return hit.group(1) if hit else None


def expand_env(value: Any, env: Mapping[str, str]) -> Any:
    """递归展开字符串里的 ${VAR} / ${VAR:-默认值}；未定义且无默认值的变量展开为空字符串。"""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: env.get(m.group(1)) or m.group(2) or "", value)
    if isinstance(value, list):
        return [expand_env(v, env) for v in value]
    if isinstance(value, dict):
        return {k: expand_env(v, env) for k, v in value.items()}
    return value


def _availability(entry: dict[str, Any]) -> tuple[bool, str | None]:
    if not str(entry.get("api_key") or "").strip():
        return False, "api_key not configured"
    if entry.get("link", "openai_compat") == "openai_compat" and not str(entry.get("api_base") or "").strip():
        return False, "api_base not configured"
    return True, None


def parse_registry(raw: Mapping[str, Any], env: Mapping[str, str]) -> Registry:
    """把 YAML 解析结果 + 环境变量转成 Registry（纯函数，便于测试）。"""
    return registry_from_data(expand_env(dict(raw), env), raw)


def registry_from_data(data: Mapping[str, Any], raw: Mapping[str, Any]) -> Registry:
    """展开过变量（可能叠加了网页配置）的数据 → Registry；raw 是原始 YAML，换配置时据此重建。"""
    models: dict[str, ModelEntry] = {}
    for item in data.get("models") or []:
        available, reason = _availability(item)
        entry = ModelEntry(**item, available=available, unavailable_reason=reason)
        if entry.alias in models:
            raise ValueError(f"duplicate model alias: {entry.alias}")
        models[entry.alias] = entry
    groups = {str(k): [str(a) for a in v] for k, v in (data.get("groups") or {}).items()}
    for group, members in groups.items():
        unknown = [a for a in members if a not in models]
        if unknown:
            raise ValueError(f"group '{group}' references unknown models: {unknown}")
    settings = RegistrySettings(**(data.get("settings") or {}))
    return Registry(models=models, groups=groups, settings=settings, source=dict(raw))


def load_registry(path: Path, env: Mapping[str, str]) -> Registry:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return parse_registry(raw, env)
