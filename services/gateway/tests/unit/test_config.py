"""配置读取：空字符串的环境变量按「未设置」处理。

回归用例：.env 里写成 `GATEWAY_TIMEOUT_SECONDS=   # 注释` 时，Docker Compose 曾把注释当作值传入，
导致容器启动失败。现在 .env.example 不再写行尾注释，同时 Settings 忽略空值。
"""

import pytest

from app.config import Settings


def test_empty_env_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_TIMEOUT_SECONDS", "")
    settings = Settings(_env_file=None)
    assert settings.gateway_timeout_seconds == 30


def test_explicit_env_value_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_TIMEOUT_SECONDS", "12.5")
    settings = Settings(_env_file=None)
    assert settings.gateway_timeout_seconds == 12.5
