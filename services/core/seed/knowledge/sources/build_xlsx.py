"""生成行业包示例 Excel：GPU 与整机参数表（不含价格，价格只在 catalog.json）。

运行：uv run python seed/knowledge/sources/build_xlsx.py
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "app" / "packs" / "llm_deploy" / "knowledge" / "GPU与整机参数表.xlsx"

GPUS = [
    ["型号", "显存", "显存类型", "FP8 支持", "典型功耗", "适用场景"],
    ["L20", "48 GB", "GDDR6", "支持", "275 W", "32B 及以下模型推理，性价比高"],
    ["H20", "96 GB", "HBM3", "支持", "400 W", "70B 以上模型、长上下文和高并发推理"],
]
SERVERS = [
    ["SKU", "配置", "GPU", "卡数", "总显存", "典型可部署模型（FP8）", "说明"],
    [
        "SRV-L20-2",
        "2 卡 L20 服务器",
        "L20",
        2,
        "96 GB",
        "Qwen3-14B / Qwen3-32B（低并发）",
        "经济方案起步配置",
    ],
    [
        "SRV-L20-4",
        "4 卡 L20 服务器",
        "L20",
        4,
        "192 GB",
        "Qwen3-32B（50 人以内并发）",
        "标准方案常用配置",
    ],
    [
        "SRV-L20-8",
        "8 卡 L20 服务器",
        "L20",
        8,
        "384 GB",
        "Qwen3-32B 高并发 / 70B 低并发",
        "单机放不下时横向扩展",
    ],
    [
        "SRV-H20-4",
        "4 卡 H20 服务器",
        "H20",
        4,
        "384 GB",
        "Llama-3.3-70B、Qwen3-32B 长上下文",
        "长文本场景优先",
    ],
    [
        "SRV-H20-8",
        "8 卡 H20 服务器",
        "H20",
        8,
        "768 GB",
        "DeepSeek-V3 量化版、70B 高并发",
        "高配方案",
    ],
]
FAQ = [
    ["问题", "回答"],
    [
        "L20 和 H20 怎么选？",
        "32B 以下优先 L20（性价比高）；70B 以上或单请求上下文超过 32K 时选 H20。",
    ],
    ["为什么卡数只能是 1、2、4、8？", "张量并行要求卡数整除注意力头数，主流模型按 2 的幂切分。"],
    ["高可用怎么配？", "两台同配置服务器加负载均衡，单台故障时另一台承接流量。"],
]


def write_sheet(wb: Workbook, title: str, rows: list[list[object]], first: bool = False) -> None:
    ws = wb.active if first else wb.create_sheet()
    assert ws is not None
    ws.title = title
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)


def main() -> None:
    wb = Workbook()
    write_sheet(wb, "GPU 卡", GPUS, first=True)
    write_sheet(wb, "整机配置", SERVERS)
    write_sheet(wb, "选型问答", FAQ)
    wb.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
