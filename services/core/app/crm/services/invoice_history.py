"""开票历史查询：回款计划视图里按时间倒序列出申请、登记、作废记录。"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crm.models import InvoiceEvent
from app.crm.schemas.finance import InvoiceEventOut
from app.crm.services import lookup


def events_of(db: Session, contract_id: uuid.UUID) -> list[InvoiceEventOut]:
    stmt = (
        select(InvoiceEvent)
        .where(InvoiceEvent.contract_id == contract_id)
        .order_by(InvoiceEvent.created_at.desc(), InvoiceEvent.id)
    )
    rows = list(db.scalars(stmt))
    actors = lookup.users(db, (r.actor_id for r in rows))
    return [
        InvoiceEventOut.model_validate(
            {
                **{f: getattr(r, f) for f in InvoiceEventOut.model_fields if hasattr(r, f)},
                "actor": lookup.pick(actors, r.actor_id),
            }
        )
        for r in rows
    ]
