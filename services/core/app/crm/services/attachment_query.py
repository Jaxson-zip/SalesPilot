"""附件查询：按挂载对象列出附件（AttachmentOut.url 指向受权限保护的下载接口）。"""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crm.models import Attachment
from app.crm.schemas.common import AttachmentOut


def file_url(attachment_id: uuid.UUID) -> str:
    return f"/api/attachments/{attachment_id}/file"


def to_out(a: Attachment) -> AttachmentOut:
    return AttachmentOut(
        id=a.id,
        kind=a.kind,  # type: ignore[arg-type]
        file_name=a.file_name,
        mime=a.mime,
        size=a.size,
        url=file_url(a.id),
    )


def rows_for(db: Session, owner_type: str, owner_ref_id: uuid.UUID) -> list[Attachment]:
    stmt = (
        select(Attachment)
        .where(Attachment.owner_type == owner_type, Attachment.owner_ref_id == owner_ref_id)
        .order_by(Attachment.created_at, Attachment.id)
    )
    return list(db.scalars(stmt).all())


def list_for(db: Session, owner_type: str, owner_ref_id: uuid.UUID) -> list[AttachmentOut]:
    return [to_out(a) for a in rows_for(db, owner_type, owner_ref_id)]


def counts(db: Session, owner_type: str, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
    wanted = list(ids)
    if not wanted:
        return {}
    stmt = (
        select(Attachment.owner_ref_id, func.count())
        .where(Attachment.owner_type == owner_type, Attachment.owner_ref_id.in_(wanted))
        .group_by(Attachment.owner_ref_id)
    )
    return {ref: int(n) for ref, n in db.execute(stmt).all()}
