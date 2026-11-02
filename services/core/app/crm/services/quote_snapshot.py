"""报价对外内容快照：项目范围、条款、回款计划、有效期。

草稿按商机当前的需求清单、条款模板和规则显示；提交审批时固化到 quote.snapshot，
之后改需求、改条款模板或规则，已发给客户的这一版（分享页、打印版、成交生成的合同）不跟着变。
- 项目范围按这一档、调整后的明细算（行业包的 quote_scope）：经济版只列首期模块和实际报价的端，
  其余写进「不包含」；
- 回款计划（结构化的期次和比例）和条款里的文字同一来源，成交时合同按它拆期；
- 有效期在提交时定下来，之后改「报价有效天数」不影响这一版。
迁移前已提交的报价没有快照：第一次生成分享链接或成交时补上。
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crm.models import Opportunity, Quote, QuoteItem
from app.crm.services import template_service
from app.packs.registry import get_configurator, get_pack
from app.rules.crm_calc import quote_valid_until
from app.rules.loader import PaymentStage, RuleSet, load_rules

EXCLUDED_KEY = "excluded_modules"  # 有这个键说明范围已按档位算过（旧快照存的是整份需求）


def _rules(quote: Quote) -> RuleSet:
    return load_rules(get_pack(quote.pack).rules_file, scope=quote.pack)


def _requirement(db: Session, quote: Quote) -> dict[str, Any] | None:
    """商机上「已确认」且同一行业包的需求清单（data 部分）；没有返回 None。"""
    opp = db.get(Opportunity, quote.opportunity_id) if quote.opportunity_id else None
    req = (opp.requirement or {}) if opp else {}
    data = req.get("data")
    if not req.get("confirmed") or req.get("pack") != quote.pack or not isinstance(data, dict):
        return None
    return data


def _tier_scope(db: Session, quote: Quote, data: dict[str, Any]) -> dict[str, Any]:
    """行业包提供 quote_scope 就按档位和明细算；没有（或需求清单不合法）原样返回。"""
    fn = getattr(get_configurator(quote.pack), "quote_scope", None)
    if not callable(fn):
        return data
    # 直接查明细（quote_query 列表要用有效期，反过来依赖本模块）
    stmt = select(QuoteItem.sku, QuoteItem.name).where(QuoteItem.quote_id == quote.id)
    items = [(sku, name) for sku, name in db.execute(stmt)]
    try:
        return dict(fn(data, quote.tier, items))
    except ValueError:  # 需求清单不完整（pydantic 校验失败）：不猜范围
        return data


def live_scope(db: Session, quote: Quote) -> dict[str, Any] | None:
    data = _requirement(db, quote)
    return _tier_scope(db, quote, data) if data is not None else None


def _valid_until(quote: Quote, rules: RuleSet, today: date) -> date:
    """报价日 + 有效天数；已经过期（过期后退回草稿续期再提交）就从今天重新算。"""
    until = quote_valid_until(quote.created_at, rules)
    return until if until >= today else today + timedelta(days=rules.quote.valid_days)


def freeze(db: Session, quote: Quote, today: date) -> None:
    """按当前需求、条款和规则固化（提交审批时调用；退回草稿再提交会重新固化）。"""
    rules = _rules(quote)
    quote.snapshot = {
        "scope": live_scope(db, quote),
        "terms": template_service.quote_terms(quote.pack),
        "payment_schedule": [s.model_dump() for s in rules.payment.schedule],
        "valid_until": _valid_until(quote, rules, today).isoformat(),
    }


def ensure_frozen(db: Session, quote: Quote, today: date) -> None:
    """发给客户、成交前确认已固化（迁移前提交的报价补一份）。"""
    if quote.snapshot is None and quote.status != "draft":
        freeze(db, quote, today)


def scope_of(db: Session, quote: Quote) -> dict[str, Any] | None:
    if quote.snapshot is None:
        return live_scope(db, quote)
    scope = quote.snapshot.get("scope")
    if not isinstance(scope, dict):
        return None
    # 上一版快照存的是整份需求：按（提交后不再变的）明细补算档位范围
    return scope if EXCLUDED_KEY in scope else _tier_scope(db, quote, scope)


def terms_of(quote: Quote) -> list[str]:
    if quote.snapshot is not None:
        return [str(t) for t in quote.snapshot.get("terms") or []]
    return template_service.quote_terms(quote.pack)


def payment_schedule_of(quote: Quote) -> list[PaymentStage]:
    """成交时合同的回款期次：报价固化的那一版；没有固化的按当前规则。"""
    raw = (quote.snapshot or {}).get("payment_schedule")
    if raw:
        return [PaymentStage.model_validate(s) for s in raw]
    return list(_rules(quote).payment.schedule)


def valid_until_of(quote: Quote) -> date:
    raw = (quote.snapshot or {}).get("valid_until")
    return date.fromisoformat(raw) if raw else quote_valid_until(quote.created_at, _rules(quote))
