"""报价单调价（接口契约 v3 §14）：仅负责人、仅草稿（含审批驳回退回的草稿）。

传入调整后的完整明细（sku + 数量）和整单折扣率；单价、成本沿用原明细，新增物料取行业包目录价；
也可以加目录以外的费用（sku 以 extra- 开头，自己填名称、单价、成本）。
总价、毛利、折扣全部由 app.rules.crm_calc.price_quote 重算；是否需要审批在提交时按规则判定
（毛利低于底线或折扣超过 discount.max_rate → 进入审批，审批 reason 写明触发的是哪条规则）。
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_owner
from app.crm.models import Quote, QuoteItem
from app.crm.schemas.quote import QUOTE_STATUS_LABELS, QuoteDetail, QuoteItemsUpdate, QuoteLineIn
from app.crm.services import activity_service, quote_query
from app.crm.services.quote_service import get_quote, rules_for
from app.packs.base import BomItem, Catalog
from app.packs.registry import get_pack
from app.rules.crm_calc import PricedLine, price_quote

RULE_NOT_EDITABLE = "quote_not_editable"


def _catalog(pack: str) -> Catalog | None:
    path = get_pack(pack).path / "catalog.json"
    return Catalog.from_file(path) if path.exists() else None


def _invalid(message: str, sku: str) -> BizError:
    return BizError(
        ErrorCode.VALIDATION,
        message,
        {"errors": [{"loc": ["body", "items"], "msg": message, "sku": sku}]},
    )


def build_lines(
    existing: list[QuoteItem], catalog: Catalog | None, data: QuoteItemsUpdate
) -> list[BomItem]:
    """按 sku 组装新明细：已有物料沿用原单价 / 成本，新增物料取目录价；重复或未知 sku → 40001。"""
    by_sku = {i.sku: i for i in existing}
    lines: list[BomItem] = []
    seen: set[str] = set()
    for line in data.items:
        if line.sku in seen:
            raise _invalid(f"物料重复：{line.sku}", line.sku)
        seen.add(line.sku)
        old = by_sku.get(line.sku)
        if line.is_extra:
            lines.append(_extra_line(line))
        elif old is not None:
            lines.append(
                BomItem(
                    sku=old.sku, name=old.name, category=old.category,  # type: ignore[arg-type]
                    unit=old.unit, qty=line.qty, unit_cost=old.unit_cost,
                    unit_price=old.unit_price,
                )
            )  # fmt: skip
        elif catalog is not None and line.sku in {c.sku for c in catalog.all()}:
            lines.append(catalog.line(line.sku, line.qty))
        else:
            raise _invalid(f"物料不在报价单或行业包目录中：{line.sku}", line.sku)
    return lines


def _extra_line(line: QuoteLineIn) -> BomItem:
    """自己加的费用：名称、单价必填；成本不填按 0（毛利照常计算，低于底线照常走审批）。"""
    if not line.name or line.unit_price is None:
        raise _invalid("自己加的费用要填写名称和单价", line.sku)
    return BomItem(
        sku=line.sku,
        name=line.name.strip(),
        category=line.category or "service",
        unit=(line.unit or "项").strip(),
        qty=line.qty,
        unit_cost=line.unit_cost or 0,
        unit_price=line.unit_price,
    )


def _check_editable(quote: Quote) -> None:
    if quote.status != "draft":
        current = QUOTE_STATUS_LABELS.get(quote.status, quote.status)
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报价单当前为「{current}」，只有草稿可以调价",
            {"rule": RULE_NOT_EDITABLE, "status": quote.status},
        )


def update_items(
    db: Session, user: CurrentUser, quote_id: uuid.UUID, data: QuoteItemsUpdate
) -> QuoteDetail:
    quote = db.get(Quote, quote_id, with_for_update=True)
    ensure_owner(quote, user)
    assert quote is not None
    _check_editable(quote)
    lines = build_lines(quote_query.items_of(db, quote.id), _catalog(quote.pack), data)
    priced = price_quote(
        [PricedLine(qty=i.qty, unit_cost=i.unit_cost, unit_price=i.unit_price) for i in lines],
        data.discount_rate,
        rules_for(quote),
    )
    db.execute(delete(QuoteItem).where(QuoteItem.quote_id == quote.id))
    base = datetime.now(UTC)  # 明细按 created_at 排序：逐行错开 1 微秒保持传入顺序
    db.add_all(
        QuoteItem(quote_id=quote.id, created_at=base + timedelta(microseconds=n), **i.model_dump())
        for n, i in enumerate(lines)
    )
    quote.total_cost, quote.total_price = priced.total_cost, priced.total_price
    quote.margin_rate, quote.discount_rate = priced.margin_rate, priced.discount_rate
    db.flush()
    content = (
        f"调整报价明细：折扣 {priced.discount_rate:.1%}，"
        f"总价 ¥{priced.total_price / 100:,.0f}，毛利 {priced.margin_rate:.1%}"
    )
    activity_service.record(db, user, "quote", quote.id, "update", content, subject=quote)
    return get_quote(db, user, quote.id)
