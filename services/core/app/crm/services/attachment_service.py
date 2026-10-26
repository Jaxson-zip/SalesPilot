"""票据附件 service（接口契约 §5）：上传 / 删除 / 下载。

- 类型：jpg / png / pdf（按文件头识别，扩展名需一致），单个 ≤ 10 MB，否则 40001
  （阈值在 rules.yaml 的 attachment 段）
- 只能给草稿状态的报销单上传或删除票据（否则 42201 expense_not_editable）
- 下载按挂载对象（报销单）的数据范围校验，看不到返回 40401
"""

import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.common import storage
from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.crm.models import Attachment, Expense
from app.crm.schemas.common import AttachmentOut
from app.crm.services import activity_service, attachment_query
from app.crm.services.expense_service import load_expense, load_owned
from app.rules import load_rules

RULE_NOT_EDITABLE = "expense_not_editable"
KINDS = ("invoice", "receipt", "other")


def _invalid(field: str, msg: str) -> BizError:
    return BizError(ErrorCode.VALIDATION, msg, {"errors": [{"loc": ["body", field], "msg": msg}]})


def _ensure_draft(expense: Expense) -> None:
    if expense.status != "draft":
        raise BizError(
            ErrorCode.RULE_VIOLATION,
            "报销单已提交，不能再修改票据",
            {"rule": RULE_NOT_EDITABLE, "status": expense.status},
        )


def validate_file(file_name: str, content: bytes, max_bytes: int, allowed: list[str]) -> str:
    """校验大小、类型与扩展名，返回识别出的 mime。"""
    if not content:
        raise _invalid("file", "文件为空")
    if len(content) > max_bytes:
        raise _invalid("file", f"文件不能超过 {max_bytes // (1024 * 1024)} MB")
    mime = storage.detect_mime(content[:16])
    if mime is None or mime not in allowed or not storage.name_matches(file_name, mime):
        raise _invalid("file", "只支持 jpg / png / pdf 文件")
    return mime


def upload(
    db: Session,
    user: CurrentUser,
    expense_id: uuid.UUID,
    kind: str,
    file_name: str,
    stream: BinaryIO,
) -> AttachmentOut:
    if kind not in KINDS:
        raise _invalid("kind", "kind 只能是 invoice / receipt / other")
    expense = load_owned(db, user, expense_id)
    _ensure_draft(expense)
    rules = load_rules().attachment
    content = stream.read(rules.max_bytes + 1)
    safe_name = Path(file_name or "file").name[:200]
    mime = validate_file(safe_name, content, rules.max_bytes, rules.allowed_types)
    attachment_id = uuid.uuid4()
    key = f"expense/{expense.id}/{attachment_id}{storage.extension_of(mime)}"
    storage.save(key, content)
    attachment = Attachment(
        id=attachment_id,
        owner_type="expense",
        owner_ref_id=expense.id,
        kind=kind,
        file_name=safe_name,
        mime=mime,
        size=len(content),
        storage_key=key,
        owner_id=expense.owner_id,
        team_id=expense.team_id,
    )
    db.add(attachment)
    db.flush()
    activity_service.record(
        db,
        user,
        "expense",
        expense.id,
        "attachment_added",
        f"上传票据 {safe_name}",
        subject=expense,
    )
    return attachment_query.to_out(attachment)


def _load(db: Session, user: CurrentUser, attachment_id: uuid.UUID) -> tuple[Attachment, Expense]:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.owner_type != "expense":
        raise BizError(ErrorCode.NOT_FOUND, "附件不存在")
    expense = load_expense(db, user, attachment.owner_ref_id)
    return attachment, expense


def delete(db: Session, user: CurrentUser, attachment_id: uuid.UUID) -> None:
    attachment, expense = _load(db, user, attachment_id)
    expense = load_owned(db, user, expense.id)
    _ensure_draft(expense)
    key, name = attachment.storage_key, attachment.file_name
    db.delete(attachment)
    db.flush()
    activity_service.record(
        db, user, "expense", expense.id, "attachment_removed", f"删除票据 {name}", subject=expense
    )
    storage.remove(key)


def file_for_download(
    db: Session, user: CurrentUser, attachment_id: uuid.UUID
) -> tuple[Path, str, str]:
    """返回 (本地路径, mime, 文件名)；文件丢失时返回 40401。"""
    attachment, _ = _load(db, user, attachment_id)
    path = storage.path_of(attachment.storage_key)
    if not path.is_file():
        raise BizError(ErrorCode.NOT_FOUND, "附件文件不存在")
    return path, attachment.mime, attachment.file_name
