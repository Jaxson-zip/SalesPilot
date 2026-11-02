"""报价单手工编辑：自己从零新建草稿；调价（接口契约 v3 §14，仅负责人、仅草稿，
含审批驳回退回的草稿）。

传入完整明细和整单折扣率；成本沿用原明细，新增物料取行业包目录（含网页上改过的价格）；
单价可以改（不传沿用原价）；也可以加目录以外的费用（sku 以 extra- 开头，自己填名称、单价、成本）。
总价、毛利、折扣全部由 app.rules.crm_calc.price_quote 重算；是否需要审批在提交时按规则判定
（毛利低于底线或折扣超过 discount.max_rate → 进入审批，审批 reason 写明触发的是哪条规则）。
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer, ensure_owner
from app.crm.models import Customer, Quote, QuoteItem
from app.crm.schemas.opportunity import StageChange
from app.crm.schemas.quote import (
    QUOTE_STATUS_LABELS,
    QuoteCreate,
    QuoteDetail,
    QuoteItemsUpdate,
    QuoteLineIn,
)
from app.crm.services import activity_service, quote_query, quote_validity
from app.crm.services.codes import next_code
from app.crm.services.opportunity_service import apply_stage, get_owned
from app.crm.services.quote_service import BEFORE_PROPOSAL, get_quote, rules_for
from app.packs.base import PASSTHROUGH, BomItem, Catalog
from app.packs.registry import get_pack
from app.rules import load_rules
from app.rules.crm_calc import PricedLine, QuotePricing, price_quote

RULE_NOT_EDITABLE = "quote_not_editable"


def _catalog(pack: str) -> Catalog | None:
    path = get_pack(pack).path / "catalog.json"
    # scope：用管理员在网页上改过的目录价，和 AI 出方案时一致
    return Catalog.from_file(path, scope=pack) if path.exists() else None


def _invalid(message: str, sku: str) -> BizError:
    return BizError(
        ErrorCode.VALIDATION,
        message,
        {"errors": [{"loc": ["body", "items"], "msg": message, "sku": sku}]},
    )


def build_lines(
    existing: list[QuoteItem], catalog: Catalog | None, data: QuoteItemsUpdate | QuoteCreate
) -> list[BomItem]:
    """按 sku 组装新明细：已有物料沿用原单价 / 成本，新增物料取目录价，传了单价就用传的；
    重复或未知 sku → 40001。"""
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
                    unit_price=old.unit_price if line.unit_price is None else line.unit_price,
                )
            )  # fmt: skip
        elif catalog is not None and line.sku in {c.sku for c in catalog.all()}:
            item = catalog.line(line.sku, line.qty)
            if line.unit_price is not None:
                item = item.model_copy(update={"unit_price": line.unit_price})
            lines.append(item)
        else:
            raise _invalid(f"物料不在报价单或行业包目录中：{line.sku}", line.sku)
    if all(i.category == PASSTHROUGH for i in lines):
        raise _invalid("报价不能只有代垫费用，至少要有一项物料或服务", lines[0].sku)
    return lines


def _extra_line(line: QuoteLineIn) -> BomItem:
    """自己加的费用：名称、单价必填；成本不填按 0（毛利照常计算，低于底线照常走审批）。
    代垫费用按成本价收：成本固定等于单价。"""
    if not line.name or line.unit_price is None:
        raise _invalid("自己加的费用要填写名称和单价", line.sku)
    passthrough = line.category == PASSTHROUGH
    return BomItem(
        sku=line.sku,
        name=line.name.strip(),
        category=line.category or "service",
        unit=(line.unit or "项").strip(),
        qty=line.qty,
        unit_cost=line.unit_price if passthrough else (line.unit_cost or 0),
        unit_price=line.unit_price,
    )


def priced_lines(lines: list[BomItem]) -> list[PricedLine]:
    return [
        PricedLine(
            qty=i.qty,
            unit_cost=i.unit_cost,
            unit_price=i.unit_price,
            passthrough=i.category == PASSTHROUGH,
        )
        for i in lines
    ]


def _check_editable(quote: Quote) -> None:
    if quote.status != "draft":
        current = QUOTE_STATUS_LABELS.get(quote.status, quote.status)
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            f"报价单当前为「{current}」，只有草稿可以调价",
            {"rule": RULE_NOT_EDITABLE, "status": quote.status},
        )


def _price(lines: list[BomItem], discount_rate: float, quote: Quote) -> QuotePricing:
    return price_quote(priced_lines(lines), discount_rate, rules_for(quote))


def _save_lines(db: Session, quote: Quote, lines: list[BomItem]) -> None:
    db.execute(delete(QuoteItem).where(QuoteItem.quote_id == quote.id))
    base = datetime.now(UTC)  # 明细按 created_at 排序：逐行错开 1 微秒保持传入顺序
    db.add_all(
        QuoteItem(quote_id=quote.id, created_at=base + timedelta(microseconds=n), **i.model_dump())
        for n, i in enumerate(lines)
    )


def _price_changes(existing: list[QuoteItem], lines: list[BomItem]) -> list[str]:
    """改过单价的已有物料，写进动态让主管看得到：「GPU 服务器 ¥128,000→¥120,000」"""
    before = {i.sku: i for i in existing}
    return [
        f"{i.name} ¥{before[i.sku].unit_price / 100:,.0f}→¥{i.unit_price / 100:,.0f}"
        for i in lines
        if i.sku in before and before[i.sku].unit_price != i.unit_price
    ]


def create_manual(db: Session, user: CurrentUser, data: QuoteCreate) -> QuoteDetail:
    """不经过 AI 新建草稿报价：选客户（或商机）、产品线，自己填明细。
    是否要审批照常在提交时按规则判定。"""
    ensure_business_writer(user)
    opp = get_owned(db, user, data.opportunity_id) if data.opportunity_id else None
    quote_validity.ensure_deal_open(db, data.opportunity_id, "出报价")
    if opp is None:
        if data.customer_id is None:
            raise BizError(
                ErrorCode.VALIDATION,
                "请选择客户或商机",
                {"errors": [{"loc": ["body", "customer_id"], "msg": "请选择客户或商机"}]},
            )
        ensure_owner(db.get(Customer, data.customer_id), user)  # 只能给自己负责的客户出报价
    lines = build_lines([], _catalog(data.pack), data)
    priced = price_quote(
        priced_lines(lines),
        data.discount_rate,
        load_rules(get_pack(data.pack).rules_file, scope=data.pack),
    )
    quote = Quote(
        code=next_code(db, Quote.code, "Q"),
        opportunity_id=opp.id if opp else None,
        customer_id=opp.customer_id if opp else data.customer_id,
        pack=data.pack,
        tier="custom",
        status="draft",
        total_cost=priced.total_cost,
        total_price=priced.total_price,
        margin_rate=priced.margin_rate,
        discount_rate=priced.discount_rate,
        client_costs=[],
        source="manual",
        owner_id=user.id,
        team_id=user.team_id,
    )
    db.add(quote)
    db.flush()
    _save_lines(db, quote, lines)
    db.flush()
    activity_service.record(
        db, user, "quote", quote.id, "create", f"新建报价单 {quote.code}", subject=quote
    )
    if opp is not None and opp.stage in BEFORE_PROPOSAL:
        apply_stage(db, user, opp, StageChange(stage="proposal"))
    return get_quote(db, user, quote.id)


def update_items(
    db: Session, user: CurrentUser, quote_id: uuid.UUID, data: QuoteItemsUpdate
) -> QuoteDetail:
    quote = db.get(Quote, quote_id, with_for_update=True)
    ensure_owner(quote, user)
    assert quote is not None
    _check_editable(quote)
    existing = quote_query.items_of(db, quote.id)
    lines = build_lines(existing, _catalog(quote.pack), data)
    priced = _price(lines, data.discount_rate, quote)
    changes = _price_changes(existing, lines)
    _save_lines(db, quote, lines)
    quote.total_cost, quote.total_price = priced.total_cost, priced.total_price
    quote.margin_rate, quote.discount_rate = priced.margin_rate, priced.discount_rate
    db.flush()
    content = (
        f"调整报价明细：折扣 {priced.discount_rate:.1%}，"
        f"总价 ¥{priced.total_price / 100:,.0f}，毛利 {priced.margin_rate:.1%}"
    )
    if changes:
        content += "；改单价：" + "，".join(changes)
    activity_service.record(db, user, "quote", quote.id, "update", content, subject=quote)
    return get_quote(db, user, quote.id)
