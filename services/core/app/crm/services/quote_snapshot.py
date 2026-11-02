"""报价对外内容快照：项目范围（已确认的需求清单）和条款。

草稿按商机当前的需求清单和条款模板显示；提交审批时固化到 quote.snapshot，
之后改需求、改条款模板或规则，已发给客户的这一版（分享页、打印版）不跟着变。
迁移前已提交的报价没有快照：第一次生成分享链接时补上。
"""

from typing import Any

from sqlalchemy.orm import Session

from app.crm.models import Opportunity, Quote
from app.crm.services import template_service


def live_scope(db: Session, quote: Quote) -> dict[str, Any] | None:
    """商机上「已确认」且同一行业包的需求清单（data 部分）；没有返回 None。"""
    opp = db.get(Opportunity, quote.opportunity_id) if quote.opportunity_id else None
    req = (opp.requirement or {}) if opp else {}
    data = req.get("data")
    if not req.get("confirmed") or req.get("pack") != quote.pack or not isinstance(data, dict):
        return None
    return data


def freeze(db: Session, quote: Quote) -> None:
    """按当前需求和条款固化（提交审批时调用；退回草稿再提交会重新固化）。"""
    quote.snapshot = {
        "scope": live_scope(db, quote),
        "terms": template_service.quote_terms(quote.pack),
    }


def ensure_frozen(db: Session, quote: Quote) -> None:
    """发给客户前确认已固化（迁移前提交的报价补一份）。"""
    if quote.snapshot is None and quote.status != "draft":
        freeze(db, quote)


def scope_of(db: Session, quote: Quote) -> dict[str, Any] | None:
    if quote.snapshot is not None:
        scope = quote.snapshot.get("scope")
        return scope if isinstance(scope, dict) else None
    return live_scope(db, quote)


def terms_of(quote: Quote) -> list[str]:
    if quote.snapshot is not None:
        return [str(t) for t in quote.snapshot.get("terms") or []]
    return template_service.quote_terms(quote.pack)
