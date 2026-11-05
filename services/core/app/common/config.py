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
    # 访问口令：公网演示时设置，登录页要先输入口令才能进入；为空表示不需要（本地开发）
    access_code: str | None = None
    # 登录页显示演示账户（一键进入、左下角切换）；正式使用时关掉，只能账号密码登录
    demo_login: bool = True
    # 部署在 nginx 后面时设为 true：来源 IP 读 nginx 写入的 X-Real-IP（登录锁定、操作日志用）。
    # 不在代理后面时必须保持 false，否则客户端伪造这个请求头就能绕过错误次数锁定
    trust_proxy_headers: bool = False
    # 定时任务调度器（到期提醒、回款逾期、日报催交等）；测试和只读副本设为 false
    scheduler_enabled: bool = True
    # 演示账户的初始密码（迁移 0019 和种子数据写入）
    demo_password: str = "demo2026"
    # 构建时写入的版本（CI 传入提交 SHA），/api/health 返回，发布后核对线上跑的是哪个版本
    app_version: str = "dev"
    llm_gateway_base: str = "http://localhost:8100/v1"
    llm_gateway_key: str = "change-me"
    llm_default_group: str = "chat-agent"
    llm_embed_group: str = "embed"
    llm_rerank_group: str = "rerank"
    rag_rerank: bool = True  # 检索后经网关重排；重排不可用时自动退回向量顺序
    llm_timeout_seconds: float = 30
    # 网页上填写的模型 Key 的加密密钥（openssl rand -hex 32）。没设置时退回用 JWT_SECRET 派生
    model_keys_secret: str = ""
    # 模型接口地址可以指向内网 / 本机（自建 vLLM、Ollama）。不写时：演示模式允许，正式模式禁止
    model_allow_private_base: bool | None = None
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
