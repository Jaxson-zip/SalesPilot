"""结构化日志：每个请求一行 JSON。

字段：request_id、别名（请求的 model）、实际模型、耗时、token、是否切换、做了哪些降级 / 修复、状态。
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

LOGGER_NAME = "gateway"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level.upper())
    return logger


@dataclass
class CallLog:
    """一次网关调用的日志记录，在路由过程中逐步填充。"""

    request_id: str
    endpoint: str
    requested_model: str
    stream: bool = False
    actual_model: str | None = None
    fallback: bool = False
    attempts: list[dict[str, Any]] = field(default_factory=list)
    downgrades: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    pseudo_stream: bool = False
    usage: dict[str, Any] | None = None
    status: str = "ok"
    error_code: str | None = None
    started: float = field(default_factory=time.perf_counter)

    def emit(self) -> None:
        data = asdict(self)
        data["latency_ms"] = round((time.perf_counter() - data.pop("started")) * 1000, 1)
        level = logging.INFO if self.status == "ok" else logging.WARNING
        logging.getLogger(LOGGER_NAME).log(level, "llm_call", extra={"fields": data})
