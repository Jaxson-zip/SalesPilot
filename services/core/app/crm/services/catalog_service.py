"""行业包产品目录（仅管理员可改）：改名称 / 单位 / 成本 / 售价，恢复默认，近期成交价对照。

默认值在 catalog.json，网页上的改动存在 config_overrides 表（scope=行业包 id，key=catalog.<sku>）。
改价只影响之后新建的方案和报价：报价明细保存了当时的单价。改了什么写进操作日志。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.crm.models import Quote, QuoteItem
from app.crm.services import audit_service
from app.crm.services.settings_service import _invalid, _require_admin, _save
from app.packs.base import Catalog, CatalogItem
from app.packs.registry import PackInfo, get_pack
from app.rules import load_rules, overrides
from app.rules.crm_calc import deal_unit_price

CATALOG_FIELDS = ("name", "unit", "cost", "price")
FIELD_LABELS = {"name": "名称", "unit": "单位", "cost": "成本", "price": "售价"}


class CatalogRow(CatalogItem):
    default_cost: int
    default_price: int
    overridden: bool
    # 最近 quote.deal_price_days 天客户接受的报价里，这个产品的成交均价（分，已扣整单折扣）
    deal_price: int | None = None
    deal_quotes: int = 0


class CatalogEdit(BaseModel):
    name: str | None = None
    unit: str | None = None
    cost: int | None = None
    price: int | None = None


def _deal_prices(db: Session, pack_id: str) -> dict[str, tuple[int | None, int]]:
    """sku → (成交均价, 涉及的报价单数)。"""
    days = load_rules().quote.deal_price_days
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(QuoteItem.sku, QuoteItem.unit_price, QuoteItem.qty, Quote.discount_rate, Quote.id)
        .join(Quote, Quote.id == QuoteItem.quote_id)
        .where(Quote.pack == pack_id, Quote.status == "accepted", Quote.updated_at >= since)
    )
    lines: dict[str, list[tuple[int, int, float]]] = {}
    quotes: dict[str, set[object]] = {}
    for sku, price, qty, discount, quote_id in db.execute(stmt):
        lines.setdefault(sku, []).append((price, qty, discount or 0.0))
        quotes.setdefault(sku, set()).add(quote_id)
    return {sku: (deal_unit_price(rows), len(quotes[sku])) for sku, rows in lines.items()}


def catalog_rows(pack: PackInfo, db: Session | None = None) -> list[CatalogRow]:
    """产品目录（含网页上的改价）；传了 db 时附上近期成交均价。"""
    path = pack.path / "catalog.json"
    if not path.exists():
        return []
    defaults = {i.sku: i for i in Catalog.from_file(path).all()}
    edited = overrides.nested(pack.id, "catalog").get("catalog", {})
    deals = _deal_prices(db, pack.id) if db is not None else {}
    return [
        CatalogRow(
            **i.model_dump(),
            default_cost=defaults[i.sku].cost,
            default_price=defaults[i.sku].price,
            overridden=i.sku in edited,
            deal_price=deals.get(i.sku, (None, 0))[0],
            deal_quotes=deals.get(i.sku, (None, 0))[1],
        )
        for i in Catalog.from_file(path, scope=pack.id).all()
    ]


def _show(field: str, value: Any) -> str:
    return f"¥{int(value) / 100:,.2f}" if field in ("cost", "price") else str(value)


def change_text(name: str, before: dict[str, Any], after: dict[str, Any]) -> str:
    """操作日志里的一句话：「GPU 服务器：售价 ¥3,000.00 → ¥1,000.00」；没变化返回空串。"""
    parts = [
        f"{FIELD_LABELS[f]} {_show(f, before[f])} → {_show(f, after[f])}"
        for f in CATALOG_FIELDS
        if before[f] != after[f]
    ]
    return f"{name}：{'，'.join(parts)}" if parts else ""


def update_catalog_item(
    db: Session, user: CurrentUser, pack_id: str, sku: str, body: CatalogEdit | None
) -> list[CatalogRow]:
    """改名称 / 单位 / 成本 / 售价（分）；body 为 None 时恢复默认。

    物料的增删依赖配置器的选型逻辑，仍在文件里维护。
    """
    _require_admin(user)
    pack = get_pack(pack_id)
    path = pack.path / "catalog.json"
    items = {i.sku: i for i in Catalog.from_file(path).all()} if path.exists() else {}
    base = items.get(sku)
    if base is None:
        raise BizError(ErrorCode.NOT_FOUND, f"产品不存在：{sku}")
    key = f"catalog.{sku}"
    current = {
        **base.model_dump(),
        **overrides.nested(pack_id, "catalog").get("catalog", {}).get(sku, {}),
    }
    if body is None:
        audit_service.note(change_text(str(current["name"]), current, base.model_dump()))
        _save(db, user, pack_id, {key: None}, {})
        return catalog_rows(pack, db)
    merged = {**current, **body.model_dump(exclude_none=True)}
    if not str(merged["name"]).strip() or not str(merged["unit"]).strip():
        raise _invalid("name", "名称和单位不能为空")
    if merged["cost"] < 0 or merged["price"] <= 0:
        raise _invalid("price", "成本不能为负数，售价必须大于 0")
    clean = {
        f: (str(merged[f]).strip() if f in ("name", "unit") else int(merged[f]))
        for f in CATALOG_FIELDS
    }
    diff = {f: v for f, v in clean.items() if v != getattr(base, f)}
    audit_service.note(change_text(str(current["name"]), current, clean))
    _save(db, user, pack_id, {key: diff or None}, {})
    return catalog_rows(pack, db)
