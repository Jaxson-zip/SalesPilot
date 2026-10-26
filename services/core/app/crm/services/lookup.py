"""批量把 id 解析成简要对象（UserBrief / CustomerBrief / OppBrief / ProductLineBrief）。

列表接口先查主表，再按 id 批量取名称，避免每个 service 都写一遍多表 join。
调用方负责主表的数据范围过滤；这里只取名称，不返回敏感字段。
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crm.models import Customer, Opportunity, ProductLine, User
from app.crm.schemas.common import CustomerBrief, OppBrief, ProductLineBrief, UserBrief


def _ids(values: Iterable[uuid.UUID | None]) -> set[uuid.UUID]:
    return {v for v in values if v is not None}


def users(db: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, UserBrief]:
    wanted = _ids(ids)
    if not wanted:
        return {}
    rows = db.execute(select(User.id, User.name).where(User.id.in_(wanted))).all()
    return {r.id: UserBrief(id=r.id, name=r.name) for r in rows}


def customers(db: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, CustomerBrief]:
    wanted = _ids(ids)
    if not wanted:
        return {}
    rows = db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(wanted))).all()
    return {r.id: CustomerBrief(id=r.id, name=r.name) for r in rows}


def opportunities(db: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, OppBrief]:
    wanted = _ids(ids)
    if not wanted:
        return {}
    stmt = select(Opportunity.id, Opportunity.name).where(Opportunity.id.in_(wanted))
    return {r.id: OppBrief(id=r.id, name=r.name) for r in db.execute(stmt).all()}


def product_lines(
    db: Session, ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID, ProductLineBrief]:
    wanted = _ids(ids)
    if not wanted:
        return {}
    stmt = select(ProductLine).where(ProductLine.id.in_(wanted))
    return {
        p.id: ProductLineBrief(id=p.id, name=p.name, pack=p.pack) for p in db.scalars(stmt).all()
    }


def pick[T](mapping: dict[uuid.UUID, T], key: uuid.UUID | None) -> T | None:
    return mapping.get(key) if key is not None else None
