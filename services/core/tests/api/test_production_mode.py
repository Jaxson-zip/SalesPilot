"""正式上线相关：启动前配置检查、来源 IP 不可伪造、演示账号公开密码拦截、初始化管理员命令。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.common import preflight
from app.common.config import Settings, get_settings
from app.common.db import session_scope
from app.common.passwords import verify_password
from app.crm.models import User
from seed import admin as seed_admin
from tests.api import test_accounts_api
from tests.api.test_accounts_api import login

cleanup = test_accounts_api.cleanup  # 复用账号测试的清理 fixture

STRONG = "x" * 40


def test_preflight_flags_default_secrets() -> None:
    weak = Settings(
        _env_file=None,
        jwt_secret="change-me",
        llm_gateway_key="change-me",
        database_url="postgresql+psycopg://crm:crm@db:5432/crm",
    )
    assert len(preflight.problems(weak)) == 4
    strong = Settings(
        _env_file=None,
        jwt_secret=STRONG,
        llm_gateway_key=STRONG,
        model_keys_secret=STRONG,
        database_url=f"postgresql+psycopg://crm:{STRONG}@db:5432/crm",
    )
    assert preflight.problems(strong) == []


def test_forged_forwarded_header_does_not_bypass_lockout(client: TestClient, cleanup: dict) -> None:
    for i in range(10):
        client.post(
            "/api/auth/login",
            json={"username": "wanglei", "password": "bad-pass1"},
            headers={"X-Forwarded-For": f"10.0.0.{i}", "X-Real-IP": f"10.0.1.{i}"},
        )
    locked = client.post(
        "/api/auth/login",
        json={"username": "wanglei", "password": "bad-pass1"},
        headers={"X-Forwarded-For": "10.9.9.9", "X-Real-IP": "10.9.9.9"},
    )
    assert locked.status_code == 429


def test_trusted_proxy_header_separates_clients(
    client: TestClient, cleanup: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "trust_proxy_headers", True)
    for _ in range(10):
        client.post(
            "/api/auth/login",
            json={"username": "wanglei", "password": "bad-pass1"},
            headers={"X-Real-IP": "203.0.113.1"},
        )
    other = client.post(
        "/api/auth/login",
        json={"username": "wanglei", "password": "bad-pass1"},
        headers={"X-Real-IP": "203.0.113.2"},
    )
    assert other.status_code == 401  # 另一个来源不受牵连


def test_demo_password_blocked_in_production_mode(
    client: TestClient, cleanup: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    password = get_settings().demo_password
    assert login(client, "zhangchen", password)["code"] == 0
    monkeypatch.setattr(get_settings(), "demo_login", False)
    r = client.post("/api/auth/login", json={"username": "zhangchen", "password": password})
    assert r.status_code == 403 and r.json()["data"]["rule"] == "demo_password"
    assert "seed.admin zhangchen" in r.json()["message"]


def test_seed_admin_creates_then_resets(client: TestClient, cleanup: dict) -> None:
    username = f"boot{uuid.uuid4().hex[:6]}"
    first, created = seed_admin.upsert_admin(username, "上线管理员")
    with session_scope() as db:
        user = db.scalars(select(User).where(func.lower(User.username) == username)).one()
        cleanup["users"].append(user.id)
        assert created and user.role == "admin" and user.must_change_password
    r = login(client, username, first)
    assert r["code"] == 0 and r["data"]["user"]["must_change_password"] is True
    second, created = seed_admin.upsert_admin(username, None)
    assert not created and second != first
    with session_scope() as db:
        user = db.scalars(select(User).where(func.lower(User.username) == username)).one()
        assert verify_password(second, user.password_hash) and user.token_version == 1
