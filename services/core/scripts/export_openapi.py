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
    return spec


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
