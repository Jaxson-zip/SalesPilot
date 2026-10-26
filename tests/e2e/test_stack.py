"""端到端测试：对正在运行的 docker compose 环境发真实请求，验证 web → core → gateway → db 的配合。

运行前：docker compose up -d && docker compose exec core python -m seed
运行：  uv run --with httpx --with pytest pytest tests/e2e -q
服务没启动时整组测试自动 skip。不需要模型 Key：网关没有可用模型时，core 会退回模板回复。
"""

from __future__ import annotations

import json
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

WEB = "http://127.0.0.1:3000"
CORE = "http://127.0.0.1:8000"
GATEWAY = "http://127.0.0.1:8100"
ROOT = Path(__file__).resolve().parents[2]


def _up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not (_up(f"{CORE}/health") and _up(f"{GATEWAY}/health")),
    reason="docker compose 环境没有启动",
)


def login(role: str, base: str = WEB) -> dict[str, str]:
    r = httpx.post(f"{base}/api/auth/mock-login", json={"role": role}, timeout=10)
    body = r.json()
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['token']}"}


def sse(path: str, payload: dict[str, object], headers: dict[str, str]) -> Iterator[tuple[str, dict]]:
    """POST 一个 SSE 接口，逐个产出 (event, data)。"""
    with httpx.stream("POST", f"{WEB}{path}", json=payload, headers=headers, timeout=120) as r:
        assert r.status_code == 200, r.read()
        event = ""
        for line in r.iter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event:
                yield event, json.loads(line.split(":", 1)[1])
                event = ""


# ---------- 健康检查与鉴权 ----------


def test_all_services_healthy() -> None:
    assert _up(f"{WEB}/dashboard")
    core = httpx.get(f"{CORE}/health").json()["data"]
    assert core["db"] is True, "core 连不上数据库"


def test_gateway_rejects_requests_without_internal_key() -> None:
    r = httpx.get(f"{GATEWAY}/v1/models")
    assert r.status_code == 401
    assert r.json()["error"]["gateway_code"] == 40101


def test_core_rejects_missing_token() -> None:
    body = httpx.get(f"{WEB}/api/me").json()
    assert body["code"] == 40101


# ---------- 数据权限（销售看本人 / 主管看团队） ----------


def _customers(role: str, view: str) -> list[dict]:
    r = httpx.get(f"{WEB}/api/customers", params={"view": view}, headers=login(role))
    body = r.json()
    assert body["code"] == 0, body
    return body["data"]["items"]


def test_sales_only_sees_own_customers() -> None:
    names = {c["name"] for c in _customers("sales", "mine")}
    assert "深圳明理律师事务所" in names
    assert "鹏城第三人民医院" not in names  # 属于同组销售王磊


def test_manager_sees_whole_team() -> None:
    names = {c["name"] for c in _customers("manager", "team")}
    assert {"深圳明理律师事务所", "鹏城第三人民医院"} <= names


def test_sales_cannot_open_other_sales_customer() -> None:
    other = next(c for c in _customers("manager", "team") if c["name"] == "鹏城第三人民医院")
    body = httpx.get(f"{WEB}/api/customers/{other['id']}", headers=login("sales")).json()
    assert body["code"] == 40401  # 不返回 40301，避免泄露记录是否存在


def test_amounts_are_integer_fen() -> None:
    for c in _customers("sales", "mine"):
        assert isinstance(c["opportunity_amount"], int)


# ---------- Agent：出方案 → 毛利回退 → 确认 → 写入报价单 ----------


def test_agent_solution_flow_with_confirmation() -> None:
    headers = login("sales")
    thread = f"e2e-{uuid.uuid4().hex[:8]}"
    message = "给明理律所出一份 Qwen3-32B 私有化方案，50 人并发，预算 40 万以内"
    events = list(sse("/api/agent/chat", {"thread_id": thread, "message": message}, headers))
    names = [e for e, _ in events]

    assert "node.retry" in names, "经济版毛利不达标时应回退重配"
    tiers = [d for e, d in events if e == "artifact" and d["type"] == "solution_tiers"][-1]["data"]
    assert all(t["margin_ok"] for t in tiers), "回退后三档毛利都应达标"
    interrupt = next(d for e, d in events if e == "interrupt")
    assert interrupt["action"] == "generate_quote"
    assert interrupt["preview"]["total_price"] == 37_200_000  # 标准版 ¥372,000，与原型一致

    resumed = list(sse("/api/agent/resume", {"thread_id": thread, "decision": "approve"}, headers))
    assert "tool.error" not in [e for e, _ in resumed], resumed
    assert any(e == "artifact" and d["type"] == "quote" for e, d in resumed)
    assert resumed[-1][0] == "done"


def test_other_user_cannot_resume_thread() -> None:
    thread = f"e2e-{uuid.uuid4().hex[:8]}"
    message = "给明理律所出一份 Qwen3-32B 私有化方案，50 人并发"
    list(sse("/api/agent/chat", {"thread_id": thread, "message": message}, login("sales")))
    r = httpx.post(
        f"{WEB}/api/agent/resume",
        json={"thread_id": thread, "decision": "approve"},
        headers=login("manager"),
        timeout=30,
    )
    assert r.json()["code"] in (40301, 40401)


# ---------- 请求 ID 透传到网关 ----------


def test_request_id_reaches_gateway() -> None:
    request_id = f"e2e-{uuid.uuid4().hex}"
    headers = {**login("sales"), "X-Request-ID": request_id}
    list(sse("/api/agent/chat", {"thread_id": request_id, "message": "你好"}, headers))
    logs = subprocess.run(
        ["docker", "compose", "logs", "gateway", "--since", "2m"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout
    assert request_id in logs, "core 调用网关时应透传 X-Request-ID"
