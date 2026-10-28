"""重排：/v1/rerank 接口、响应整理、模型种类隔离。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.compat.errors import GatewayError
from app.compat.response import normalize_rerank
from app.config import Settings
from app.main import create_app
from tests.fakes import FakeBackend, make_registry

KEY = "test-internal-key"
AUTH = {"Authorization": f"Bearer {KEY}"}
DOCS = ["住宿标准：一线城市每晚 500 元", "客户招待按人均 150 元执行", "交通：高铁二等座"]


def _client(script: dict[str, list[Any]]) -> tuple[TestClient, FakeBackend]:
    backend = FakeBackend(script)
    app = create_app(registry=make_registry(), backend=backend, settings=Settings(gateway_internal_key=KEY))
    return TestClient(app), backend


def test_normalize_rerank_sorts_and_accepts_vendor_shapes() -> None:
    cohere = {"results": [{"index": 0, "relevance_score": 0.2}, {"index": 1, "relevance_score": 0.9}]}
    assert [r["index"] for r in normalize_rerank(cohere, "m", 3)["results"]] == [1, 0]
    dashscope = {"output": {"results": [{"index": 2, "score": 0.7}, {"index": 9, "score": 0.99}]}}
    out = normalize_rerank(dashscope, "m", 3)
    assert out["results"] == [{"index": 2, "relevance_score": 0.7}]  # 越界的 index 丢弃


def test_rerank_endpoint_fails_over_within_group() -> None:
    upstream_error = GatewayError(502, 50201, "boom", "api_error", "upstream_error")
    ok = {"results": [{"index": 1, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.3}]}
    client, backend = _client({"m-rerank": [upstream_error, upstream_error], "m-rerank-b": [ok]})
    body = {"model": "rerank", "query": "请客户吃饭能报多少", "documents": DOCS, "top_n": 2}
    resp = client.post("/v1/rerank", json=body, headers=AUTH)
    assert resp.status_code == 200, resp.text
    assert resp.json()["model"] == "m-rerank-b"
    assert [r["index"] for r in resp.json()["results"]] == [1, 0]
    assert backend.calls[-1][1] == {"query": body["query"], "documents": DOCS, "top_n": 2}


@pytest.mark.parametrize(("endpoint", "model"), [("/v1/rerank", "m-tools"), ("/v1/embeddings", "m-rerank")])
def test_model_kinds_are_not_mixed(endpoint: str, model: str) -> None:
    """对话模型不能拿来重排，重排模型也不能拿来做 Embedding。"""
    client, _ = _client({})
    body: dict[str, Any] = {"model": model, "query": "q", "documents": DOCS, "input": "x"}
    resp = client.post(endpoint, json=body, headers=AUTH)
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "capability_mismatch"


def test_rerank_models_excluded_from_chat_groups_and_listed_with_capability() -> None:
    reg = make_registry()
    assert [m.alias for m in reg.resolve("rerank", kind="rerank")] == ["m-rerank", "m-rerank-b"]
    client, _ = _client({})
    data = {m["id"]: m for m in client.get("/v1/models", headers=AUTH).json()["data"]}
    assert data["rerank"]["capabilities"]["rerank"] is True
    assert data["m-rerank"]["capabilities"]["tools"] is False
