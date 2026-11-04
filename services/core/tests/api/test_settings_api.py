"""网页上维护的配置：通用规则、行业包参数、产品价格、知识库上传（需要数据库）。"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.common.db import session_scope
from app.crm.models import AuditLog, ConfigOverride, Quote, QuoteItem
from app.packs.registry import get_configurator
from app.rules import load_rules, overrides
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H


@pytest.fixture(autouse=True)
def clean_overrides() -> Iterator[None]:
    """每个用例前后清空网页改动，恢复文件默认值。"""

    def wipe() -> None:
        with session_scope() as db:
            db.execute(delete(ConfigOverride))
            db.flush()
            overrides.refresh(db)

    wipe()
    yield
    wipe()


def _field(data: dict, key: str) -> dict:
    return next(f for f in data["fields"] if f["key"] == key)


def test_only_admin(client: TestClient) -> None:
    for h in (SALES_H, MANAGER_H):
        assert client.get("/api/settings/rules", headers=h).json()["code"] == 40301
        body = {"values": {"margin.floor_rate": 0.2}}
        assert client.put("/api/settings/rules", json=body, headers=h).json()["code"] == 40301


def test_global_rule_edit_takes_effect_and_resets(client: TestClient) -> None:
    data = client.get("/api/settings/rules", headers=ADMIN_H).json()["data"]
    assert "报价与审批" in data["groups"]
    floor = _field(data, "margin.floor_rate")
    assert floor["label"] == "毛利底线" and floor["value"] == 0.25 and not floor["overridden"]

    body = {"values": {"margin.floor_rate": 0.2, "expense.hotel.tier1_cities": ["北京", " 杭州 "]}}
    res = client.put("/api/settings/rules", json=body, headers=ADMIN_H).json()
    assert res["code"] == 0
    floor = _field(res["data"], "margin.floor_rate")
    assert floor["value"] == 0.2 and floor["default"] == 0.25 and floor["overridden"]
    assert floor["updated_by"]  # 记录是谁改的
    # 立即生效：通用规则和行业包规则（行业包没有单独设置时沿用通用）
    assert load_rules().margin.floor_rate == 0.2
    assert get_configurator("llm_deploy").rules.margin.floor_rate == 0.2
    assert load_rules().expense.hotel and load_rules().expense.hotel.tier1_cities == [
        "北京",
        "杭州",
    ]

    reset = {"values": {"margin.floor_rate": None}}
    res = client.put("/api/settings/rules", json=reset, headers=ADMIN_H).json()
    assert not _field(res["data"], "margin.floor_rate")["overridden"]
    assert load_rules().margin.floor_rate == 0.25


@pytest.mark.parametrize(
    ("values", "msg"),
    [
        ({"margin.floor_rate": 1.5}, "超出允许范围"),
        ({"quote.valid_days": 2.5}, "整数"),
        ({"unknown.key": 1}, "不能在网页上修改"),
        (
            {"payment.schedule": [{"name": "预付款", "ratio": 0.5, "due_days": 0}]},
            "合计必须是 100%",
        ),
    ],
)
def test_validation(client: TestClient, values: dict, msg: str) -> None:
    res = client.put("/api/settings/rules", json={"values": values}, headers=ADMIN_H)
    assert res.status_code == 400 and msg in res.json()["message"]


def test_payment_schedule_edit(client: TestClient) -> None:
    stages = [
        {"name": "预付款", "ratio": 0.5, "due_days": 0},
        {"name": "尾款", "ratio": 0.5, "due_days": 90},
    ]
    res = client.put(
        "/api/settings/rules", json={"values": {"payment.schedule": stages}}, headers=ADMIN_H
    ).json()
    assert res["code"] == 0
    assert [s.name for s in load_rules().payment.schedule] == ["预付款", "尾款"]


def test_pack_settings_override_global(client: TestClient) -> None:
    data = client.get("/api/packs/llm_deploy/settings", headers=ADMIN_H).json()["data"]
    keys = [f["key"] for f in data["fields"]]
    assert "margin.floor_rate" in keys and "pack.vram_headroom" in keys
    body = {"values": {"margin.floor_rate": 0.3, "pack.vram_headroom": 1.5}}
    res = client.put("/api/packs/llm_deploy/settings", json=body, headers=ADMIN_H).json()
    assert res["code"] == 0
    cfg = get_configurator("llm_deploy")
    assert cfg.rules.margin.floor_rate == 0.3 and cfg.params["vram_headroom"] == 1.5
    assert load_rules().margin.floor_rate == 0.25  # 通用不受影响
    assert get_configurator("it_office").rules.margin.floor_rate == 0.25


def test_catalog_price_edit_and_reset(client: TestClient) -> None:
    res = client.put(
        "/api/packs/llm_deploy/catalog/SRV-L20-4",
        json={"price": 30_000_000},
        headers=ADMIN_H,
    ).json()
    row = next(r for r in res["data"] if r["sku"] == "SRV-L20-4")
    assert row["price"] == 30_000_000 and row["default_price"] == 26_200_000 and row["overridden"]
    assert get_configurator("llm_deploy").catalog.get("SRV-L20-4").price == 30_000_000

    bad = client.put("/api/packs/llm_deploy/catalog/SRV-L20-4", json={"price": 0}, headers=ADMIN_H)
    assert bad.status_code == 400
    missing = client.put("/api/packs/llm_deploy/catalog/NOPE", json={"price": 1}, headers=ADMIN_H)
    assert missing.json()["code"] == 40401

    res = client.delete("/api/packs/llm_deploy/catalog/SRV-L20-4", headers=ADMIN_H).json()
    row = next(r for r in res["data"] if r["sku"] == "SRV-L20-4")
    assert row["price"] == 26_200_000 and not row["overridden"]


def _catalog_audit(action: str) -> str | None:
    with session_scope() as db:
        row = db.scalars(
            select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at.desc())
        ).first()
        return row.detail if row else None


def test_catalog_edit_records_old_and_new_price(client: TestClient) -> None:
    """回归：改价的操作日志只记了谁改的，没记从多少改成多少，查不到价格历史。"""
    url = "/api/packs/llm_deploy/catalog/SRV-L20-4"
    assert client.put(url, json={"price": 30_000_000}, headers=ADMIN_H).json()["code"] == 0
    assert _catalog_audit("pack.catalog") == "GPU 服务器 4× L20 48G：售价 ¥262,000.00 → ¥300,000.00"
    assert client.delete(url, headers=ADMIN_H).json()["code"] == 0
    assert _catalog_audit("pack.catalog_reset") == (
        "GPU 服务器 4× L20 48G：售价 ¥300,000.00 → ¥262,000.00"
    )
    # 被拒的请求照常记失败原因
    assert client.put(url, json={"price": 1}, headers=SALES_H).json()["code"] == 40301


def _row(client: TestClient, sku: str) -> dict:
    detail = client.get("/api/packs/it_office", headers=SALES_H).json()["data"]
    return next(r for r in detail["catalog"] if r["sku"] == sku)


def test_catalog_shows_recent_deal_price(client: TestClient) -> None:
    before = _row(client, "MON-27-4K")
    with session_scope() as db:
        q = Quote(
            code=f"Q-DEAL-{uuid.uuid4().hex[:6]}",
            pack="it_office",
            tier="standard",
            status="accepted",
            discount_rate=0.1,
            updated_at=datetime.now(UTC),
        )
        db.add(q)
        db.flush()
        db.add(
            QuoteItem(
                quote_id=q.id,
                sku="MON-27-4K",
                name="显示器",
                unit="台",
                qty=4,
                unit_cost=180_000,
                unit_price=240_000,
                category="hardware",
            )
        )
        quote_id = q.id
    try:
        after = _row(client, "MON-27-4K")
        assert after["deal_quotes"] == before["deal_quotes"] + 1
        if before["deal_quotes"] == 0:
            assert after["deal_price"] == 216_000  # 2400 元 9 折
    finally:
        with session_scope() as db:
            db.execute(delete(QuoteItem).where(QuoteItem.quote_id == quote_id))
            db.execute(delete(Quote).where(Quote.id == quote_id))


def test_knowledge_upload_and_delete(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.crm.services import settings_service

    monkeypatch.setattr(settings_service, "uploaded_dir", lambda pack: tmp_path / pack)
    monkeypatch.setattr(
        settings_service, "embed_texts", lambda texts: [[0.0] * 1024 for _ in texts]
    )
    from app.crm.services import pack_service  # noqa: F401  知识库列表也走 uploaded_dir

    doc = "# 测试上传文档\n\n## 售后\n\n上门服务 4 小时响应。".encode()
    files = {"file": ("售后说明.md", BytesIO(doc), "text/markdown")}
    res = client.post("/api/packs/it_office/knowledge", files=files, headers=ADMIN_H).json()
    assert res["code"] == 0 and res["data"]["chunks"] >= 1

    detail = client.get("/api/packs/it_office", headers=ADMIN_H).json()["data"]
    doc_row = next(d for d in detail["knowledge"] if d["doc_name"] == "售后说明.md")
    assert doc_row["source"] == "uploaded" and doc_row["chunks"] >= 1

    dup = {"file": ("售后说明.md", BytesIO(doc), "text/markdown")}
    assert (
        client.post("/api/packs/it_office/knowledge", files=dup, headers=ADMIN_H).json()["code"]
        == 40901
    )
    txt = {"file": ("a.txt", BytesIO(b"x"), "text/plain")}
    assert (
        client.post("/api/packs/it_office/knowledge", files=txt, headers=ADMIN_H).status_code == 400
    )

    res = client.delete("/api/packs/it_office/knowledge/售后说明.md", headers=ADMIN_H).json()
    assert res["code"] == 0
    detail = client.get("/api/packs/it_office", headers=ADMIN_H).json()["data"]
    assert all(d["doc_name"] != "售后说明.md" for d in detail["knowledge"])
    # 内置文档不能在网页上删除
    builtin = detail["knowledge"][0]["doc_name"]
    res = client.delete(f"/api/packs/it_office/knowledge/{builtin}", headers=ADMIN_H).json()
    assert res["code"] == 40401


def test_knowledge_upload_embedding_down(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """向量模型上游故障：报上游错误、不留文件，列表里不会出现「看得到却搜不到」的文档。"""
    from app.common.errors import ErrorCode
    from app.crm.services import settings_service

    monkeypatch.setattr(settings_service, "uploaded_dir", lambda pack: tmp_path / pack)

    def down(_texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embed upstream 502")

    monkeypatch.setattr(settings_service, "embed_texts", down)
    doc = "# 上游故障\n\n## 说明\n\n测试内容。".encode()
    files = {"file": ("上游故障.md", BytesIO(doc), "text/markdown")}
    res = client.post("/api/packs/it_office/knowledge", files=files, headers=ADMIN_H).json()
    assert res["code"] == ErrorCode.UPSTREAM and "文档入库失败" in res["message"]
    assert not (tmp_path / "it_office" / "上游故障.md").exists()
    detail = client.get("/api/packs/it_office", headers=ADMIN_H).json()["data"]
    assert all(d["doc_name"] != "上游故障.md" for d in detail["knowledge"])


def test_software_pack_settings_nested_ratio(client: TestClient) -> None:
    """软件外包：嵌套参数（pack.ratios.qa）可改，改完配置器立即按新比例估算。"""
    data = client.get("/api/packs/software_outsourcing/settings", headers=ADMIN_H).json()["data"]
    keys = {f["key"] for f in data["fields"]}
    assert {"pack.team_size", "pack.ratios.qa", "pack.extra_platform_factor"} <= keys
    body = {"values": {"pack.ratios.qa": 0.4, "pack.team_size": 2}}
    res = client.put("/api/packs/software_outsourcing/settings", json=body, headers=ADMIN_H).json()
    assert res["code"] == 0
    cfg = get_configurator("software_outsourcing")
    assert cfg.params["ratios"]["qa"] == 0.4 and cfg.params["ratios"]["ui"] == 0.15
    assert cfg.params["team_size"] == 2
