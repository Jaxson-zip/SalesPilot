"""注册表：${ENV} 展开、可用性、分组解析、能力不匹配（差异 #12）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.compat.errors import GatewayError
from app.config import SERVICE_DIR
from app.registry import expand_env, load_registry
from tests.fakes import make_registry


def test_expand_env_nested() -> None:
    data = {"a": "${X}/v1", "b": ["${Y}", 3], "c": "${NOPE}"}
    assert expand_env(data, {"X": "http://h", "Y": "k"}) == {"a": "http://h/v1", "b": ["k", 3], "c": ""}


def test_model_without_key_is_unavailable() -> None:
    reg = make_registry()
    assert reg.models["m-tools"].available
    assert not reg.models["m-nokey"].available
    assert reg.models["m-nokey"].unavailable_reason == "api_key not configured"
    assert reg.models["m-tools"].litellm_model == "openai/x"


def test_diff12_group_skips_unavailable_and_non_tool_models() -> None:
    reg = make_registry()
    assert [m.alias for m in reg.resolve("g-agent")] == ["m-plain", "m-tools", "m-pseudo"]
    assert [m.alias for m in reg.resolve("g-agent", needs_tools=True)] == ["m-tools", "m-pseudo"]


def test_diff12_direct_alias_without_tools_is_capability_mismatch() -> None:
    with pytest.raises(GatewayError) as info:
        make_registry().resolve("m-plain", needs_tools=True)
    assert (info.value.status, info.value.gateway_code) == (400, 40002)


def test_unknown_and_unavailable_and_embedding_checks() -> None:
    reg = make_registry()
    with pytest.raises(GatewayError) as info:
        reg.resolve("nope")
    assert info.value.status == 404
    with pytest.raises(GatewayError) as info:
        reg.resolve("m-nokey")
    assert info.value.code == "model_unavailable"
    with pytest.raises(GatewayError) as info:
        reg.resolve("m-tools", kind="embedding")
    assert info.value.gateway_code == 40002
    assert [m.alias for m in reg.resolve("embed", kind="embedding")] == ["m-embed"]


def test_project_models_yaml_loads_without_keys() -> None:
    reg = load_registry(SERVICE_DIR / "models.yaml", {})
    assert set(reg.groups) == {"chat-default", "chat-agent", "embed"}
    assert not any(m.available for m in reg.models.values())
    assert all(reg.models[a].capabilities.tools for a in reg.groups["chat-agent"])


def test_group_with_unknown_member_rejected(tmp_path: Path) -> None:
    file = tmp_path / "m.yaml"
    file.write_text("models: []\ngroups:\n  g: [ghost]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(file, {})
