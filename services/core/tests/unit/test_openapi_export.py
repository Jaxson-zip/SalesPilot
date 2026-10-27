"""docs/api/openapi.yaml 必须与代码一致：改了接口没重新导出时这个测试失败。"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_openapi.py"


def _module():
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_doc_is_up_to_date() -> None:
    m = _module()
    expected = m.render(m.build())
    assert m.OUT.read_text(encoding="utf-8") == expected, (
        "接口有变化，请运行 uv run python scripts/export_openapi.py 更新 docs/api/openapi.yaml"
    )


def test_openapi_covers_key_endpoints() -> None:
    m = _module()
    paths = set(m.build()["paths"])
    for p in (
        "/api/expenses",
        "/api/templates",
        "/api/agent/chat",
        "/api/agent/models",
        "/api/tasks",
    ):
        assert p in paths
