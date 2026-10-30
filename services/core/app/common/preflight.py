"""启动前的安全配置检查。

正式模式（DEMO_LOGIN=false）下发现问题直接拒绝启动；演示模式只打警告，方便本地开发。
"""

from sqlalchemy.engine import make_url

from app.common.config import Settings

DEFAULT_SECRETS = {"change-me", "change-me-to-a-random-string-of-32-chars"}
DEFAULT_DB_PASSWORD = "crm"
MIN_SECRET_LENGTH = 32


def problems(settings: Settings) -> list[str]:
    out = []
    if settings.jwt_secret in DEFAULT_SECRETS or len(settings.jwt_secret) < MIN_SECRET_LENGTH:
        out.append(f"JWT_SECRET 还是默认值或短于 {MIN_SECRET_LENGTH} 位")
    if len(settings.model_keys_secret) < MIN_SECRET_LENGTH:
        out.append(f"MODEL_KEYS_SECRET（模型 Key 加密密钥）没有设置或短于 {MIN_SECRET_LENGTH} 位")
    if settings.llm_gateway_key in DEFAULT_SECRETS:
        out.append("LLM_GATEWAY_KEY / GATEWAY_INTERNAL_KEY 还是默认值")
    try:
        password = make_url(settings.database_url).password
    except Exception:  # 地址格式不对交给数据库连接报错
        password = None
    if password == DEFAULT_DB_PASSWORD:
        out.append("数据库密码（POSTGRES_PASSWORD）还是默认的 crm")
    return out
