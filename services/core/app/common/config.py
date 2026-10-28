"""配置：只从环境变量（或 .env）读取，变量名与根目录 .env.example 保持一致。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 本地开发时在 services/core 下运行：依次读取仓库根目录和当前目录的 .env（环境变量优先）
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"), extra="ignore", env_ignore_empty=True
    )

    database_url: str = "postgresql+psycopg://crm:crm@localhost:5432/crm"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60 * 24
    llm_gateway_base: str = "http://localhost:8100/v1"
    llm_gateway_key: str = "change-me"
    llm_default_group: str = "chat-agent"
    llm_embed_group: str = "embed"
    llm_rerank_group: str = "rerank"
    rag_rerank: bool = True  # 检索后经网关重排；重排不可用时自动退回向量顺序
    llm_timeout_seconds: float = 30
    upload_dir: str = "./data/uploads"
    default_pack: str = "llm_deploy"
    embedding_dims: int = 1024
    db_connect_timeout_seconds: int = 3
    # 企业微信群机器人 Webhook（可选；网页「系统设置 → 消息推送」里保存的地址优先）
    wecom_webhook_url: str | None = None
    # 推送消息里的链接前缀（部署后改成对外访问的网页地址）
    web_base_url: str = "http://127.0.0.1:3005"
    # 外部情报数据源：目前只内置 demo（演示数据），接入真实数据源后改成对应的 provider 名
    intel_provider: str = "demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
