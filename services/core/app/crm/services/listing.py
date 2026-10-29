"""列表页服务端筛选的公共部分：排序、多选参数、筛选项（facets）。

列表页（客户 / 报价 / 合同 / 报销）分页、筛选、排序都在服务端做；筛选项也由服务端
在当前数据范围内统计，而不是只看已加载的一页。
"""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.crm.models import Customer, User


class SortKey(StrEnum):
    DEFAULT = "default"
    UPDATED = "updated"
    AMOUNT_DESC = "amount_desc"
    AMOUNT_ASC = "amount_asc"


class FacetOption(BaseModel):
    value: str
    label: str


def clean(values: list[str] | None) -> list[str]:
    """多选参数：去空白、去空串、去重（保持顺序）。"""
    seen: dict[str, None] = {}
    for v in values or []:
        s = v.strip()
        if s:
            seen[s] = None
    return list(seen)


def order(
    stmt: Select[Any], sort: SortKey | None, *, updated: Any, amount: Any, default: tuple[Any, ...]
) -> Select[Any]:
    """排序：最近更新（空值在后）/ 金额；同值时按默认顺序，保证翻页稳定。"""
    if sort is SortKey.UPDATED:
        return stmt.order_by(updated.desc().nulls_last(), *default)
    if sort is SortKey.AMOUNT_DESC:
        return stmt.order_by(amount.desc(), *default)
    if sort is SortKey.AMOUNT_ASC:
        return stmt.order_by(amount.asc(), *default)
    return stmt.order_by(*default)


def user_facet(db: Session, scoped: Select[Any], column: Any) -> list[FacetOption]:
    """范围内出现过的负责人（按姓名排序）。"""
    ids = scoped.with_only_columns(column).where(column.is_not(None)).distinct().scalar_subquery()
    rows = db.execute(select(User.id, User.name).where(User.id.in_(ids)).order_by(User.name))
    return [FacetOption(value=str(i), label=n) for i, n in rows]


def customer_facet(db: Session, scoped: Select[Any], column: Any) -> list[FacetOption]:
    """范围内出现过的客户（按名称排序）。"""
    ids = scoped.with_only_columns(column).where(column.is_not(None)).distinct().scalar_subquery()
    stmt = select(Customer.id, Customer.name).where(Customer.id.in_(ids)).order_by(Customer.name)
    return [FacetOption(value=str(i), label=n) for i, n in db.execute(stmt)]


def value_facet(db: Session, scoped: Select[Any], column: Any) -> list[FacetOption]:
    """范围内出现过的取值（例如行业、行业包），按出现次数从多到少。"""
    sub = scoped.with_only_columns(column).where(column.is_not(None), column != "").subquery()
    col = sub.c[0]
    stmt = select(col).group_by(col).order_by(func.count().desc(), col)
    return [FacetOption(value=v, label=v) for v in db.scalars(stmt)]


def uuids(values: list[uuid.UUID] | None) -> list[uuid.UUID]:
    return list(dict.fromkeys(values or []))
