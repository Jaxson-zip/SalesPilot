"""导出 core 的 OpenAPI 文档到 docs/api/openapi.yaml（AGENTS「完成的标准」：改了接口就同步）。

运行：uv run python scripts/export_openapi.py        # 写入
      uv run python scripts/export_openapi.py --check  # 只检查是否最新（CI / 测试用）
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parents[1] / "docs" / "api" / "openapi.yaml"
HEADER = "# 由 services/core/scripts/export_openapi.py 从 FastAPI 自动生成，请勿手改。\n"


def build() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from app.main import create_app

    spec = create_app().openapi()
    spec["info"]["description"] = (
        "SalesPilot 业务服务。统一响应 {code, message, data, request_id}；"
        "错误码见 docs/开发规范.md §8.2；字段说明见 docs/api/业务模块接口契约.md。"
    )
    mark_response_fields_required(spec)
    return spec


def _refs(node: Any) -> set[str]:
    """node 里直接引用的 schema 名。"""
    if isinstance(node, dict):
        ref = node.get("$ref")
        found = {ref.rsplit("/", 1)[-1]} if isinstance(ref, str) else set()
        return found.union(*(_refs(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(_refs(v) for v in node))
    return set()


def _closure(names: set[str], schemas: dict[str, Any]) -> set[str]:
    seen: set[str] = set()
    todo = list(names)
    while todo:
        name = todo.pop()
        if name in seen or name not in schemas:
            continue
        seen.add(name)
        todo.extend(_refs(schemas[name]))
    return seen


def mark_response_fields_required(spec: dict[str, Any]) -> None:
    """只出现在响应里的 schema：所有字段标为 required。

    后端返回时总会带上全部字段（响应不用 exclude_unset / exclude_none），值可能是 null 但不会缺；
    FastAPI 默认把有默认值的字段写成可选，前端生成的类型就会多出 undefined。
    请求里出现的 schema 保持原样（调用方可以不传有默认值的字段）。
    """
    schemas = spec.get("components", {}).get("schemas", {})
    inputs: set[str] = set()
    outputs: set[str] = set()
    for item in spec.get("paths", {}).values():
        for op in item.values():
            if not isinstance(op, dict):
                continue
            inputs |= _refs(op.get("requestBody", {})) | _refs(op.get("parameters", []))
            outputs |= _refs(op.get("responses", {}))
    inputs = _closure(inputs, schemas)
    for name in _closure(outputs, schemas) - inputs:
        props = schemas[name].get("properties", {})
        required = schemas[name].get("required", [])
        extra = [k for k in props if k not in required]
        if extra:
            schemas[name]["required"] = required + extra


def render(spec: dict[str, Any]) -> str:
    return HEADER + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="不写文件，只检查是否需要重新导出")
    args = parser.parse_args()
    text = render(build())
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            sys.exit(
                "docs/api/openapi.yaml 不是最新的，请运行 uv run python scripts/export_openapi.py"
            )
        print("openapi.yaml is up to date")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(spec_paths(text))} paths)")


def spec_paths(text: str) -> list[str]:
    return list((yaml.safe_load(text) or {}).get("paths", {}))


if __name__ == "__main__":
    main()
