"""客户样例图片上传：一次一张，视觉模型返回类型、字段名、清晰度（这里用替身模型，不调真实模型）。"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agent import samples as sample_lib
from tests.api.conftest import SALES_H

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class FakeVision:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.seen: list[Any] = []

    def invoke(self, messages: list[Any]) -> AIMessage:
        self.seen.append(messages)
        return AIMessage(content=self.reply)


def _use(monkeypatch: pytest.MonkeyPatch, reply: str, available: bool = True) -> FakeVision:
    fake = FakeVision(reply)
    monkeypatch.setattr(sample_lib, "model_available", lambda *_a, **_k: available)
    monkeypatch.setattr(sample_lib, "get_chat_model", lambda *_a, **_k: fake)
    return fake


def _post(client: TestClient, name: str, content: bytes) -> dict[str, Any]:
    r = client.post(
        "/api/agent/samples", files={"file": (name, content, "image/png")}, headers=SALES_H
    )
    return r.json()


def test_analyze_sample_image(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    reply = '{"doc_type": "装箱单", "fields": ["箱号", "毛重"], "quality": "handwritten"}'
    fake = _use(monkeypatch, reply)
    body = _post(client, "样例1.png", PNG)
    assert body["code"] == 0
    assert body["data"] == {
        "name": "样例1.png",
        "doc_type": "装箱单",
        "fields": ["箱号", "毛重"],
        "quality": "handwritten",
    }
    content = fake.seen[0][0].content
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_analyze_sample_errors(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, "{}")
    assert _post(client, "a.pdf", b"%PDF")["code"] == 40001  # 只收图片
    _use(monkeypatch, "看不清这张图")
    assert "没能识别" in _post(client, "a.png", PNG)["message"]
    _use(monkeypatch, "{}", available=False)
    assert "未配置" in _post(client, "a.png", PNG)["message"]


def test_chat_rejects_too_many_samples(client: TestClient) -> None:
    item = {"name": "a.png", "doc_type": "发票", "fields": [], "quality": "clear"}
    body = {
        "thread_id": "t-samples-limit",
        "message": "按样例出方案",
        "samples": {"total": 31, "items": [item]},
    }
    r = client.post("/api/agent/chat", json=body, headers=SALES_H)
    assert r.status_code == 400 and r.json()["code"] == 40001
