"""显存估算与 GPU 选型（纯函数，开发规范 §7 公式）。

权重显存 = 参数量 × 每参数字节数
KV Cache = 2 × 层数 × KV 维度 × 上下文长度 × 并发数 × 字节数
总显存   = (权重 + KV Cache) × 余量系数（默认 1.2）

说明：§7 原文写的是「隐藏维度」，对 GQA 模型（Qwen3、Llama3 等）实际应使用 KV 维度
（KV 头数 × 每头维度），否则 KV Cache 会被高估约 5 倍；这里按 KV 维度计算。
"""

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

MODELS_FILE = Path(__file__).parent / "knowledge" / "models.json"
GB = 1_000_000_000


class ModelSpec(BaseModel):
    name: str
    params_b: float
    layers: int
    hidden: int
    kv_heads: int
    head_dim: int
    max_context: int

    @property
    def kv_dim(self) -> int:
        return self.kv_heads * self.head_dim


class VramEstimate(BaseModel):
    model: str
    precision: str
    weights_gb: float
    kv_cache_gb: float
    total_gb: float
    formula: str


class GpuPlan(BaseModel):
    gpu_mem_gb: int
    cards_per_node: int
    nodes: int

    @property
    def total_mem_gb(self) -> int:
        return self.gpu_mem_gb * self.cards_per_node * self.nodes


@lru_cache
def _load() -> dict[str, Any]:
    return json.loads(MODELS_FILE.read_text(encoding="utf-8"))


def precision_bytes() -> dict[str, float]:
    return dict(_load()["precision_bytes"])


def model_specs() -> dict[str, ModelSpec]:
    return {name: ModelSpec(name=name, **spec) for name, spec in _load()["models"].items()}


def find_model(text: str) -> ModelSpec | None:
    """在文本里查找已知模型名（忽略大小写，最长匹配优先）。"""
    lowered = text.lower()
    for name in sorted(model_specs(), key=len, reverse=True):
        if name.lower() in lowered:
            return model_specs()[name]
    return None


def kv_bytes_for(precision: str) -> float:
    """KV Cache 精度：量化到 4bit 的权重仍用 FP8 KV Cache，其余与权重相同。"""
    return max(precision_bytes()[precision], 1.0)


def estimate_vram(
    spec: ModelSpec,
    precision: str,
    concurrency: int,
    context_tokens: int,
    headroom: float = 1.2,
) -> VramEstimate:
    if concurrency <= 0 or context_tokens <= 0:
        raise ValueError("并发数和上下文长度必须大于 0")
    wbytes = precision_bytes()[precision]
    kvbytes = kv_bytes_for(precision)
    weights = spec.params_b * wbytes
    kv = 2 * spec.layers * spec.kv_dim * context_tokens * concurrency * kvbytes / GB
    total = (weights + kv) * headroom
    formula = (
        f"weights = {spec.params_b}B × {wbytes} byte ≈ {weights:.1f} GB\n"
        f"kv_cache = 2 × {spec.layers} 层 × {spec.kv_heads} KV头 × {spec.head_dim} × "
        f"{context_tokens} × {concurrency} 并发 × {kvbytes} byte ≈ {kv:.1f} GB\n"
        f"total = ({weights:.1f} + {kv:.1f}) × {headroom} ≈ {total:.1f} GB"
    )
    return VramEstimate(
        model=spec.name,
        precision=precision,
        weights_gb=round(weights, 1),
        kv_cache_gb=round(kv, 1),
        total_gb=round(total, 1),
        formula=formula,
    )


def plan_gpus(total_gb: float, gpu_mem_gb: int, tp_sizes: list[int]) -> GpuPlan:
    """按张量并行规格（1/2/4/8 卡）选最小可用卡数；单机放不下时按满配机器横向扩展。"""
    cards = max(1, math.ceil(total_gb / gpu_mem_gb))
    for size in sorted(tp_sizes):
        if size >= cards:
            return GpuPlan(gpu_mem_gb=gpu_mem_gb, cards_per_node=size, nodes=1)
    max_size = max(tp_sizes)
    return GpuPlan(
        gpu_mem_gb=gpu_mem_gb, cards_per_node=max_size, nodes=math.ceil(cards / max_size)
    )
