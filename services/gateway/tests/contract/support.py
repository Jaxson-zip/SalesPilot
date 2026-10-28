"""契约测试支撑代码：开关、注册表加载、录制后端。

运行：RUN_CONTRACT=1 uv run pytest tests/contract -k <别名>
没有设置 RUN_CONTRACT=1 或对应模型没有 Key 时自动 skip。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.backend import Backend, ChatResult
from app.config import SERVICE_DIR, merged_env
from app.registry import Registry, load_registry

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
RESULTS_FILE = Path(__file__).resolve().parent / "results.json"
CONTRACT_ENABLED = os.environ.get("RUN_CONTRACT") == "1"


def project_registry() -> Registry:
    path = Path(os.environ.get("GATEWAY_MODELS_FILE", "models.yaml"))
    path = path if path.is_absolute() else SERVICE_DIR / path
    return load_registry(path, merged_env())


def chat_aliases() -> list[str]:
    try:
        reg = project_registry()
    except FileNotFoundError:
        return []
    return [a for a, m in reg.models.items() if m.is_chat]


class RecordingBackend:
    """包一层真实后端，把上游原始返回写到 tests/fixtures/<别名>/<用例>.json，供以后离线回放。"""

    def __init__(self, inner: Backend, case: str) -> None:
        self.inner = inner
        self.case = case

    def _save(self, alias: str, payload: Any) -> None:
        folder = FIXTURE_DIR / alias
        folder.mkdir(parents=True, exist_ok=True)
        data = {"_recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"), "_case": self.case, "response": payload}
        (folder / f"{self.case}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    async def _tee(self, alias: str, stream: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        try:
            async for chunk in stream:
                chunks.append(chunk)
                yield chunk
        finally:
            self._save(alias, {"chunks": chunks})

    async def chat(self, alias: str, params: dict[str, Any]) -> ChatResult:
        result = await self.inner.chat(alias, params)
        if isinstance(result, dict):
            self._save(alias, result)
            return result
        return self._tee(alias, result)

    async def embed(self, alias: str, params: dict[str, Any]) -> dict[str, Any]:
        result = await self.inner.embed(alias, params)
        self._save(alias, result)
        return result
