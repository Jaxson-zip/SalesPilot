"""大模型部署需求 schema：决定 Agent 需要追问哪些信息。"""

from pydantic import BaseModel, Field


class LlmDeployRequirement(BaseModel):
    model_name: str = Field(description="要部署的模型，例如 Qwen3-32B")
    concurrency: int = Field(gt=0, le=10000, description="并发用户数")
    scene: str | None = Field(default=None, description="业务场景，例如 合同审查")
    budget: int | None = Field(default=None, ge=0, description="预算（分）")
    context_tokens: int | None = Field(
        default=None, gt=0, le=1_000_000, description="单请求平均上下文长度（token）"
    )


# 追问时展示给用户的字段名
FIELD_LABELS: dict[str, str] = {
    "model_name": "要部署的模型（如 Qwen3-32B）",
    "concurrency": "并发用户数",
}
