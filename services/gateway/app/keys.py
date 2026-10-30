"""网页上填写的厂商 Key：core 推过来，覆盖 .env 里的同名变量，立即生效（不用重启）。

- 只接受 models.yaml 里 api_key 写成 ${VAR} 的变量名；
- 每次推送都是完整集合：没带的变量回到 .env 的值；
- 只放在内存里，网关重启后由 core 按 version 发现并重新推送；
- Key 不会出现在任何响应和日志里，测试连接的报错也会把 Key 替换掉。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.backend import Backend
from app.compat.errors import classify_exception, invalid_param
from app.registry import ModelEntry, Registry, parse_registry

# 「litellm.BadRequestError: OpenAIException - 」这类前缀对管理员没有意义
_NOISE = re.compile(r"^litellm\.\w+:\s*(\w+Exception\s*-\s*)?")


class KeyManager:
    def __init__(self, registry: Registry, backend: Backend, env: Mapping[str, str]) -> None:
        self.registry = registry
        self.backend = backend
        self.base_env = dict(env)
        self.overrides: dict[str, str] = {}
        self.version = ""  # core 存的配置版本；空 = 还没收到过

    def providers(self) -> list[dict[str, Any]]:
        out = []
        for var, aliases in self.registry.key_vars().items():
            models = [self.registry.models[a] for a in aliases if a in self.registry.models]
            out.append(
                {
                    "var": var,
                    "models": aliases,
                    "env_configured": bool(self.base_env.get(var, "").strip()),
                    "overridden": var in self.overrides,
                    "available": any(m.available for m in models),
                }
            )
        return out

    def update(self, keys: Mapping[str, str], version: str) -> None:
        known = self.registry.key_vars()
        unknown = sorted(set(keys) - set(known))
        if unknown:
            raise invalid_param(f"unknown key variables: {unknown}", "keys")
        overrides = {k: v.strip() for k, v in keys.items() if v and v.strip()}
        fresh = parse_registry(self.registry.source, {**self.base_env, **overrides})
        self.registry.replace_with(fresh)
        self.backend.reset()
        self.overrides, self.version = overrides, version

    def _probe_entry(self, var: str, key: str) -> ModelEntry:
        aliases = self.registry.key_vars().get(var)
        if not aliases:
            raise invalid_param(f"unknown key variable: {var}", "var")
        entries = [self.registry.models[a] for a in aliases]
        # 优先用对话模型测：最常用，且各家都支持
        entry = next((e for e in entries if e.is_chat), entries[0])
        # api_base 也可能引用变量：按当前生效的值展开
        current = parse_registry(self.registry.source, {**self.base_env, **self.overrides})
        return current.models[entry.alias].model_copy(update={"api_key": key})

    async def test(self, var: str, key: str | None) -> dict[str, Any]:
        """key 为空时测当前生效的 Key（网页值或 .env）。"""
        effective = key or self.overrides.get(var) or self.base_env.get(var, "")
        entry = self._probe_entry(var, effective)
        if not effective.strip():
            return {"ok": False, "model": entry.alias, "error": "没有可用的 Key"}
        if not entry.api_base and entry.link == "openai_compat":
            return {"ok": False, "model": entry.alias, "error": "接口地址（API_BASE）没有配置"}
        try:
            await self.backend.probe(entry)
        except Exception as exc:  # 把上游错误转成一句话，去掉可能回显的 Key
            message = _NOISE.sub("", classify_exception(exc).message.replace(effective, "***"))
            return {"ok": False, "model": entry.alias, "error": message[:300]}
        return {"ok": True, "model": entry.alias, "error": None}
