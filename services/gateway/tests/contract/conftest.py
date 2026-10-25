"""契约测试结果收集：写 tests/contract/results.json，供 scripts/compat_matrix.py 生成兼容矩阵。

运行：RUN_CONTRACT=1 uv run pytest tests/contract -k <别名>
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from tests.contract.support import CONTRACT_ENABLED, RESULTS_FILE

_RESULTS: dict[str, dict[str, str]] = {}


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if "tests/contract" not in report.nodeid.replace("\\", "/") or "[" not in report.nodeid:
        return
    if report.when != "call" and not (report.when == "setup" and report.outcome != "passed"):
        return
    params = report.nodeid.split("[", 1)[1].rstrip("]")
    alias, _, case = params.partition("-case_")
    status = {"passed": "pass", "failed": "fail", "skipped": "skip"}[report.outcome]
    _RESULTS.setdefault(alias, {})[case] = status


def pytest_sessionfinish(session: pytest.Session) -> None:
    if not CONTRACT_ENABLED or not _RESULTS:
        return
    existing: dict[str, Any] = {}
    if RESULTS_FILE.exists():
        existing = json.loads(RESULTS_FILE.read_text("utf-8"))
    for alias, cases in _RESULTS.items():
        if all(v == "skip" for v in cases.values()):
            continue
        existing[alias] = {"tested_at": time.strftime("%Y-%m-%d %H:%M"), "cases": cases}
    RESULTS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), "utf-8")
