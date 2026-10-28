"""根据契约测试结果生成 docs/模型兼容矩阵.md。

用法（在 services/gateway 下）：
    RUN_CONTRACT=1 uv run pytest tests/contract      # 产出 tests/contract/results.json
    uv run python scripts/compat_matrix.py           # 没有结果时生成全部「未测试」的表
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

from app.registry import Registry, load_registry  # noqa: E402

RESULTS_FILE = SERVICE_DIR / "tests" / "contract" / "results.json"
OUTPUT_FILE = SERVICE_DIR.parent.parent / "docs" / "模型兼容矩阵.md"
CASES: list[tuple[str, str]] = [
    ("chat", "普通对话"),
    ("chat_stream", "流式对话"),
    ("tool_single", "单工具调用"),
    ("tool_parallel", "并行工具调用"),
    ("tool_stream", "流式工具调用"),
    ("tool_second_turn", "工具结果回传第二轮"),
    ("json_output", "JSON 输出"),
    ("context_overflow", "上下文超长报错"),
    ("bad_key", "错误 Key 报错"),
    ("group_failover", "分组失败切换"),
]
STATUS_TEXT = {"pass": "✅ 通过", "fail": "❌ 失败", "skip": "⏭ 跳过"}
CAPS = ("stream", "tools", "stream_tools", "tool_choice_required", "parallel_tool_calls", "json_mode")


def load_results(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _yes(value: bool) -> str:
    return "✔" if value else "—"


def render(registry: Registry, results: dict[str, Any]) -> str:
    chat = [a for a, m in registry.models.items() if m.is_chat]
    lines = [
        "# 模型兼容矩阵",
        "",
        "> 由 `services/gateway/scripts/compat_matrix.py` 根据契约测试结果自动生成，请勿手改。",
        "> 用例定义见 `docs/开发规范.md` §12.1；「未测试」表示还没有用真实 Key 跑过契约测试。",
        "",
        "## 契约测试结果",
        "",
        "| 用例 | " + " | ".join(chat) + " |",
        "|---|" + "---|" * len(chat),
    ]
    for case, label in CASES:
        cells = [STATUS_TEXT.get(results.get(a, {}).get("cases", {}).get(case, ""), "未测试") for a in chat]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    tested = [results.get(a, {}).get("tested_at", "未测试") for a in chat]
    lines += ["| 测试时间 | " + " | ".join(tested) + " |", "", "## 注册表声明的能力（models.yaml）", ""]
    lines += [
        "| 别名 | 链路 | " + " | ".join(CAPS) + " | max_context |",
        "|---|---|" + "---|" * (len(CAPS) + 1),
    ]
    for alias in chat:
        entry = registry.models[alias]
        caps = entry.capabilities
        cells = [_yes(getattr(caps, c)) for c in CAPS]
        lines.append(f"| {alias} | {entry.link} | " + " | ".join(cells) + f" | {caps.max_context or '—'} |")
    lines += ["", "契约测试不通过的能力需要在 `models.yaml` 里改成 `false`，兼容层会自动降级。", ""]
    return "\n".join(lines)


def main() -> None:
    registry = load_registry(SERVICE_DIR / "models.yaml", {})
    OUTPUT_FILE.write_text(render(registry, load_results(RESULTS_FILE)), encoding="utf-8")
    print(f"written {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
