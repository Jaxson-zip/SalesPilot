"""客户 service（参考实现）：业务逻辑、数据范围过滤都在这里，router 只做参数和响应。"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer, ensure_owner
from app.common.scope import View, apply_scope, can_see, ensure_visible
from app.crm.models import Customer, Followup, Opportunity, User
from app.crm.schemas.common import Page, PageParams, UserBrief
from app.crm.schemas.customer import (
    CustomerCreate,
    CustomerDetail,
    CustomerListItem,
    CustomerSearchItem,
    CustomerUpdate,
    SimilarCustomer,
)
from app.crm.services import activity_service
from app.crm.services.listing import FacetOption, SortKey, order, user_facet, value_facet


@dataclass(frozen=True)
class CustomerFilter:
    """列表筛选：同一字段多选为「或」，不同字段为「且」；level 按首字母（A / B / C）比较。"""

    level: list[str] = field(default_factory=list)
    industry: list[str] = field(default_factory=list)
    owner_id: list[uuid.UUID] = field(default_factory=list)
    sort: SortKey | None = None


def apply_filter(stmt: Select[Any], f: CustomerFilter | None) -> Select[Any]:
    if f is None:
        return stmt
    if f.level:
        grade = func.upper(func.left(func.trim(Customer.level), 1))
        stmt = stmt.where(grade.in_([v[:1].upper() for v in f.level]))
    if f.industry:
        stmt = stmt.where(Customer.industry.in_(f.industry))
    if f.owner_id:
        stmt = stmt.where(Customer.owner_id.in_(f.owner_id))
    return stmt


def ordered(stmt: Select[Any], f: CustomerFilter | None, *default: Any) -> Select[Any]:
    """最近更新 = 最近跟进时间；金额 = 商机金额合计（都是 build_list_query 里的列）。"""
    return order(
        stmt,
        f.sort if f else None,
        updated=literal_column("last_followup_at"),
        amount=literal_column("opportunity_amount"),
        default=(*default, Customer.id),
    )


def _opportunity_amount_subq() -> Any:
    return (
        select(Opportunity.customer_id, func.sum(Opportunity.amount).label("amount"))
        .where(Opportunity.stage != "lost")
        .group_by(Opportunity.customer_id)
        .subquery("opp")
    )


def _last_followup_subq() -> Any:
    return (
        select(Followup.customer_id, func.max(Followup.created_at).label("last_at"))
        .group_by(Followup.customer_id)
        .subquery("fu")
    )


def build_list_query(
    user: CurrentUser, view: View | None, q: str | None, *, scoped: bool = True
) -> Select[Any]:
    """列表查询（不含分页）：客户 + 负责人 + 商机金额合计 + 最近跟进时间，默认按数据范围过滤。"""
    opp = _opportunity_amount_subq()
    fu = _last_followup_subq()
    stmt = (
        select(
            Customer,
            User.name.label("owner_name"),
            func.coalesce(opp.c.amount, 0).label("opportunity_amount"),
            fu.c.last_at.label("last_followup_at"),
        )
        .outerjoin(User, User.id == Customer.owner_id)
        .outerjoin(opp, opp.c.customer_id == Customer.id)
        .outerjoin(fu, fu.c.customer_id == Customer.id)
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.industry.ilike(pattern)))
    return apply_scope(stmt, Customer, user, view) if scoped else stmt


def _owner(customer: Customer, owner_name: str | None) -> UserBrief | None:
    if customer.owner_id is None or owner_name is None:
        return None
    return UserBrief(id=customer.owner_id, name=owner_name)


def to_list_item(row: Any) -> CustomerListItem:
    c: Customer = row.Customer
    return CustomerListItem(
        id=c.id,
        name=c.name,
        industry=c.industry,
        level=c.level,
        owner=_owner(c, row.owner_name),
        website=c.website,
        opportunity_amount=int(row.opportunity_amount or 0),
        last_followup_at=row.last_followup_at,
    )


def _to_detail(row: Any) -> CustomerDetail:
    c: Customer = row.Customer
    return CustomerDetail(
        **to_list_item(row).model_dump(),
        size=c.size,
        address=c.address,
        annual_budget=c.annual_budget,
        tags=list(c.tags or []),
        created_at=c.created_at,
    )


def list_customers(
    db: Session,
    user: CurrentUser,
    view: View | None,
    q: str | None,
    page: PageParams,
    f: CustomerFilter | None = None,
) -> Page[CustomerListItem]:
    base = apply_filter(build_list_query(user, view, q), f)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    stmt = ordered(base, f, Customer.created_at.desc())
    rows = db.execute(stmt.offset(page.offset).limit(page.page_size)).all()
    return Page[CustomerListItem](items=[to_list_item(r) for r in rows], total=total)


def facets(db: Session, user: CurrentUser, view: View | None) -> dict[str, list[FacetOption]]:
    """筛选项：当前范围内的行业、负责人。"""
    scoped = apply_scope(select(Customer), Customer, user, view)
    return {
        "industry": value_facet(db, scoped, Customer.industry),
        "owner": user_facet(db, scoped, Customer.owner_id),
    }


def get_customer(db: Session, user: CurrentUser, customer_id: uuid.UUID) -> CustomerDetail:
    # 不在查询里加范围：公海客户（负责人为空）本团队可见，统一由 ensure_visible 判断
    stmt = build_list_query(user, None, None, scoped=False).where(Customer.id == customer_id)
    row = db.execute(stmt).first()
    ensure_visible(row.Customer if row else None, user)
    assert row is not None
    return _to_detail(row)


def create_customer(db: Session, user: CurrentUser, data: CustomerCreate) -> CustomerDetail:
    ensure_business_writer(user)
    names = list(db.scalars(select(Customer.name)))
    same = [n for n, exact in similar_names(data.name, names) if exact]
    if same:
        raise BizError(ErrorCode.DUPLICATE, f"客户已存在：{same[0]}")
    customer = Customer(**data.model_dump(), owner_id=user.id, team_id=user.team_id)
    customer.name = data.name.strip()
    db.add(customer)
    db.flush()
    activity_service.record(db, user, "customer", customer.id, "create", customer.name)
    return get_customer(db, user, customer.id)


# 查重时忽略的公司后缀、地名括号和空白（「明理科技（深圳）有限公司」≈「明理科技」）
_NAME_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团", "公司")
_BRACKETS = re.compile(r"[（(][^）)]*[）)]")


def core_name(name: str) -> str:
    text = _BRACKETS.sub("", "".join(name.split()))
    for suffix in _NAME_SUFFIXES:  # 从长到短，只剥最长的一个
        if text.endswith(suffix):
            return text[: -len(suffix)] if len(text) > len(suffix) + 1 else text
    return text


def similar_names(name: str, candidates: list[str], limit: int = 5) -> list[tuple[str, bool]]:
    """[(候选名, 是否同名)]：核心名相同为同名；一方包含另一方，或二元字组重合 ≥ 2
    且占较短一方的一半以上，为相似。"""
    target = core_name(name)
    grams = _bigrams(target)
    scored: list[tuple[float, str, bool]] = []
    for cand in candidates:
        core = core_name(cand)
        if core == target:
            scored.append((2.0, cand, True))
            continue
        if len(target) >= 2 and (target in core or core in target):
            scored.append((1.5, cand, False))
            continue
        other = _bigrams(core)
        overlap = len(grams & other)
        shorter = min(len(grams), len(other)) or 1
        if overlap >= 2 and overlap / shorter >= 0.5:
            scored.append((overlap / shorter, cand, False))
    scored.sort(key=lambda x: -x[0])
    return [(n, exact) for _, n, exact in scored[:limit]]


def find_similar(db: Session, user: CurrentUser, name: str) -> list[SimilarCustomer]:
    """全公司范围查重（重复客户不分团队）；看不到的客户只返回名称和负责人。"""
    if len(core_name(name)) < 2:
        return []
    rows = db.execute(
        select(Customer, User.name.label("owner_name")).outerjoin(
            User, User.id == Customer.owner_id
        )
    ).all()
    by_name = {r.Customer.name: r for r in rows}
    out = []
    for cand, exact in similar_names(name, list(by_name)):
        row = by_name[cand]
        visible = can_see(row.Customer, user)
        out.append(
            SimilarCustomer(
                id=row.Customer.id if visible else None,
                name=cand,
                owner_name=row.owner_name,
                exact=exact,
                visible=visible,
            )
        )
    return out


_FIELD_LABELS = {
    "name": "名称",
    "industry": "行业",
    "level": "等级",
    "size": "规模",
    "address": "地址",
    "website": "网站",
    "annual_budget": "年度预算",
}


def update_customer(
    db: Session, user: CurrentUser, customer_id: uuid.UUID, data: CustomerUpdate
) -> CustomerDetail:
    """负责人修改客户字段（U10 行内编辑）；改名时同样按核心名查重（排除自己）。"""
    customer = db.get(Customer, customer_id)
    ensure_owner(customer, user)
    assert customer is not None
    changes = {
        k: v
        for k, v in data.model_dump(exclude_unset=True).items()
        if not (v is None and k in {"name", "level"})  # 非空字段传 null 视为不修改
    }
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        others = list(db.scalars(select(Customer.name).where(Customer.id != customer.id)))
        same = [n for n, exact in similar_names(changes["name"], others) if exact]
        if same:
            raise BizError(ErrorCode.DUPLICATE, f"客户已存在：{same[0]}")
    for key, value in changes.items():
        setattr(customer, key, value)
    if changes:
        db.flush()
        text = "、".join(_FIELD_LABELS.get(k, k) for k in changes)
        activity_service.record(db, user, "customer", customer.id, "update", text, subject=customer)
    return get_customer(db, user, customer.id)


_CITY_PREFIXES = (
    "深圳市",
    "深圳",
    "广州市",
    "广州",
    "东莞",
    "佛山",
    "珠海",
    "北京",
    "上海",
    "杭州",
)


def mention_keys(name: str) -> list[str]:
    """客户名在口语里的说法：去后缀、去城市前缀后的核心名，以及它的前 4 / 3 / 2 个字。

    「深圳明理律师事务所」→ 明理律师事务所、明理律师、明理律、明理（用户常说「明理律所」）。
    """
    key = core_name(name)
    for city in _CITY_PREFIXES:
        if key.startswith(city) and len(key) - len(city) >= 2:
            key = key[len(city) :]
            break
    return [k for k in dict.fromkeys([key, key[:4], key[:3], key[:2]]) if len(k) >= 2]


def find_mentioned(db: Session, user: CurrentUser, text: str) -> list[Customer]:
    """AI 出方案时，从用户这句话里找出提到的客户（只在自己负责的客户里找）。"""
    if not text.strip():
        return []
    mine = db.scalars(select(Customer).where(Customer.owner_id == user.id)).all()
    return [c for c in mine if any(k in text for k in mention_keys(c.name))]


def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


def rank_by_similarity(keyword: str, names: list[str], min_overlap: int = 2) -> list[str]:
    """按二元字组重合数排序（「明理律所」能匹配「深圳明理律师事务所」）。"""
    grams = _bigrams(keyword)
    scored = [(len(grams & _bigrams(n)), n) for n in names]
    return [n for score, n in sorted(scored, key=lambda x: -x[0]) if score >= min_overlap]


def _brief(row: Any) -> CustomerSearchItem:
    c: Customer = row.Customer
    return CustomerSearchItem(
        id=c.id,
        name=c.name,
        industry=c.industry,
        level=c.level,
        owner=_owner(c, row.owner_name),
    )


def search_customers(
    db: Session, user: CurrentUser, keyword: str, limit: int = 5
) -> list[CustomerSearchItem]:
    """Agent 用：在当前用户可见范围内模糊匹配客户；子串匹配不到时按字组相似度匹配。"""
    rows = db.execute(build_list_query(user, None, keyword).limit(limit)).all()
    if rows:
        return [_brief(r) for r in rows]
    candidates = db.execute(build_list_query(user, None, None).limit(500)).all()
    by_name = {r.Customer.name: r for r in candidates}
    ranked = rank_by_similarity(keyword, list(by_name))[:limit]
    return [_brief(by_name[name]) for name in ranked]


def search_by_opportunity(
    db: Session, user: CurrentUser, keyword: str, limit: int = 5
) -> list[tuple[CustomerSearchItem, str]]:
    """客户名匹配不到时按商机名找（销售常直接说「质检助手那单」）：返回 (客户, 命中的商机名)。"""
    pattern = f"%{keyword.strip()}%"
    stmt = select(Opportunity.customer_id, Opportunity.name).where(Opportunity.name.ilike(pattern))
    hits = db.execute(apply_scope(stmt, Opportunity, user).limit(limit)).all()
    names: dict[uuid.UUID, str] = {}
    for h in hits:
        names.setdefault(h.customer_id, h.name)
    if not names:
        return []
    rows = db.execute(build_list_query(user, None, None).where(Customer.id.in_(names))).all()
    return [(_brief(r), names[r.Customer.id]) for r in rows]
