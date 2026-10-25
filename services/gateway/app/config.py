"""网关配置：只从环境变量（以及可选的 .env 文件）读取。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
# 本地开发时依次查找：services/gateway/.env、仓库根目录 .env；容器里由 env_file 注入环境变量
ENV_FILES: tuple[Path, ...] = (SERVICE_DIR.parent.parent / ".env", SERVICE_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    gateway_internal_key: str = "change-me"
    gateway_models_file: str = "models.yaml"
    gateway_timeout_seconds: float = 30
    gateway_log_level: str = "INFO"

    def models_path(self) -> Path:
        """相对路径按服务目录解析，保证在任意工作目录下都能找到 models.yaml。"""
        path = Path(self.gateway_models_file)
        if path.is_absolute() or path.exists():
            return path
        return SERVICE_DIR / path


def merged_env() -> dict[str, str]:
    """用于展开 models.yaml 里的 ${VAR}：.env 文件 < 进程环境变量。"""
    env: dict[str, str] = {}
    for file in ENV_FILES:
        if file.is_file():
            env.update({k: v for k, v in dotenv_values(file).items() if v is not None})
    env.update(os.environ)
    return env


@lru_cache
def get_settings() -> Settings:
    return Settings()
