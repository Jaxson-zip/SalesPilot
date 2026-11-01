"""模型接入 schema：内置厂商、自定义厂商、默认模型分组、知识库向量重建状态。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal["chat", "embedding", "rerank"]
LinkType = Literal["openai_compat", "native"]
ProtocolChoice = Literal["", "openai_compat", "native"]


# ---------- 出参 ----------


class ModelCard(BaseModel):
    alias: str
    model: str
    link: str
    kind: Kind
    tools: bool = False
    dims: int | None = None
    available: bool
    unavailable_reason: str | None = None
    provider: str  # 厂商名（显示用）


class BuiltinOut(BaseModel):
    var: str
    label: str
    hint: str
    # web：网页上保存的；env：服务器 .env；none：都没有
    key_source: Literal["web", "env", "none"]
    tail: str | None = None
    saved_by: str | None = None
    saved_at: datetime | None = None
    # 网页上存过，但加密密钥换过、解不开了
    broken: bool = False
    base: str = ""  # 网页上改的接口地址；空 = 默认
    default_base: str = ""
    protocol: ProtocolChoice = ""  # 空 = 按模型清单（已通过契约测试）
    adapter: str = ""
    # 网关里这家的模型是否有可用的；网关连不上时为 None
    available: bool | None = None
    models: list[ModelCard] = []


class Capabilities(BaseModel):
    """自定义模型的能力：测试连接时自动检测，也可以手动改。"""

    tools: bool = False
    stream: bool = True
    stream_tools: bool = False
    json_mode: bool = False
    dims: int | None = Field(default=None, ge=1, le=8192)


class CustomModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    kind: Kind = "chat"
    capabilities: Capabilities = Field(default_factory=Capabilities)


class CustomModelOut(CustomModelIn):
    alias: str
    available: bool | None = None
    unavailable_reason: str | None = None


class CustomOut(BaseModel):
    id: str
    name: str
    protocol: LinkType
    adapter: str = ""
    api_base: str = ""
    tail: str | None = None
    has_key: bool = False
    broken: bool = False
    saved_by: str | None = None
    saved_at: datetime | None = None
    available: bool | None = None
    models: list[CustomModelOut]


class ReindexOut(BaseModel):
    status: Literal["idle", "running", "done", "failed"] = "idle"
    target: str | None = None
    done: int = 0
    total: int = 0
    error: str | None = None
    by: str | None = None
    at: datetime | None = None


class ModelConfigOut(BaseModel):
    gateway_ok: bool
    builtin: list[BuiltinOut]
    custom: list[CustomOut]
    # 当前生效的分组（chat-agent / embed / rerank → 模型别名，按顺序）和 models.yaml 的默认
    groups: dict[str, list[str]]
    group_defaults: dict[str, list[str]]
    models: list[ModelCard]
    embedding_dims: int
    kb_chunks: int
    reindex: ReindexOut
    allow_private_base: bool


class TestOut(BaseModel):
    ok: bool
    model: str | None = None
    error: str | None = None
    dims: int | None = None  # Embedding 模型的向量维度
    capabilities: dict[str, bool] | None = None  # 对话模型检测到的能力


# ---------- 入参 ----------


class BuiltinIn(BaseModel):
    var: str = Field(min_length=1, max_length=64)
    # None = 不改；空字符串 = 删除网页上保存的 Key（回到 .env）
    key: str | None = Field(default=None, max_length=500)
    base: str = Field(default="", max_length=500)
    protocol: ProtocolChoice = ""
    adapter: str = Field(default="", max_length=32)


class BuiltinTestIn(BuiltinIn):
    """表单上的值；key 不填 = 测当前生效的 Key。"""


class CustomIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    protocol: LinkType = "openai_compat"
    adapter: str = Field(default="", max_length=32)
    api_base: str = Field(default="", max_length=500)
    # None = 不改；空字符串 = 删除
    key: str | None = Field(default=None, max_length=500)
    models: list[CustomModelIn] = Field(min_length=1, max_length=20)


class CustomTestIn(BaseModel):
    protocol: LinkType = "openai_compat"
    adapter: str = Field(default="", max_length=32)
    api_base: str = Field(default="", max_length=500)
    key: str | None = Field(default=None, max_length=500)  # 不填 = 用这个厂商已保存的
    model: CustomModelIn
    detect: bool = True


class GroupsIn(BaseModel):
    chat: list[str] = Field(min_length=1, max_length=10)
    rerank: list[str] = Field(default_factory=list, max_length=10)


class EmbeddingIn(BaseModel):
    alias: str = Field(min_length=1, max_length=160)
