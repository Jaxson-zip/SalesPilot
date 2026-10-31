"""客户批量导入：CSV（UTF-8 / GBK）或 Excel，先预览（逐行校验、查重）再确认导入。

- 第一行是表头，列名见 COLUMNS（支持几个常见别名），只有「客户名称」必填。
- 查重与新建客户一致：按核心名（去掉「有限公司」、地名括号等）全公司范围比较；已存在的跳过，
  文件里重复的只导入第一行；名称相似但不相同的照常导入，给出提示。
- 销售只能导入给自己；主管可以在「负责人」列填本团队成员（姓名或账号），填「公海」放入本团队公海，
  留空归自己。管理员对业务数据只读。
- 确认导入时重新解析同一个文件，有问题的行跳过，其余行在一个事务里写入。
"""

import csv
import io
import re
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from typing import BinaryIO, Literal

from openpyxl import load_workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_business_writer
from app.crm.models import Contact, Customer, User
from app.crm.schemas.dashboard import CONTACT_ROLE_LABELS
from app.crm.schemas.fields import WEBSITE_ERROR, normalize_website, phone_error
from app.crm.services import activity_service, notification_service
from app.crm.services.customer_service import core_name, similar_names

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
POOL = "公海"

# 字段 → 表头（第一个是模板里的写法，其余是别名）
COLUMNS: dict[str, tuple[str, ...]] = {
    "name": ("客户名称", "名称", "公司名称", "客户"),
    "industry": ("行业",),
    "level": ("等级", "客户等级"),
    "size": ("规模", "公司规模"),
    "address": ("地址",),
    "website": ("网站", "官网"),
    "annual_budget": ("年度预算（元）", "年度预算", "预算"),
    "tags": ("标签",),
    "contact_name": ("联系人", "联系人姓名"),
    "contact_title": ("职位", "联系人职位"),
    "contact_phone": ("电话", "联系电话", "手机"),
    "contact_role": ("联系人角色", "角色"),
    "owner": ("负责人",),
}
MAX_LEN = {
    "name": 200,
    "industry": 50,
    "size": 50,
    "address": 200,
    "website": 200,
    "contact_name": 50,
    "contact_title": 50,
    "contact_phone": 30,
}
_ROLE_BY_LABEL = {v: k for k, v in CONTACT_ROLE_LABELS.items()}
_TAG_SPLIT = re.compile(r"[、,，;；/\s]+")
# 行的负责人：某个成员、"self"（导入人自己）、None（本团队公海）
Owner = User | Literal["self"] | None
_MONEY = re.compile(r"^(\d+(?:\.\d+)?)\s*(万)?(?:元)?$")


class ImportRow(BaseModel):
    line: int  # 文件里的行号（表头是第 1 行）
    name: str
    owner_name: str | None = None  # 导入后的负责人；None 表示公海
    status: Literal["ok", "duplicate", "error"]
    message: str | None = None  # 跳过的原因
    warnings: list[str] = []


class ImportResult(BaseModel):
    total: int
    ok: int  # 预览：可以导入的行数；导入：实际新建的客户数
    skipped: int
    created: bool  # True 表示已写入
    columns: list[str]  # 识别到的列（字段名），用于提示「没认出的列」
    ignored_columns: list[str]
    rows: list[ImportRow]


@dataclass
class _Parsed:
    line: int
    values: dict[str, str]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _cell(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _read_table(filename: str, content: bytes) -> list[list[str]]:
    is_xlsx = filename.lower().endswith(".xlsx") or content[:2] == b"PK"
    if is_xlsx:
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            raise BizError(ErrorCode.VALIDATION, "Excel 文件打不开，请另存为 .xlsx 后重试") from exc
        try:
            sheet = wb.worksheets[0]
            return [[_cell(c) for c in r] for r in sheet.iter_rows(values_only=True)]
        finally:
            wb.close()
    for encoding in ("utf-8-sig", "gb18030"):  # Excel 另存的 CSV 常是 GBK
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise BizError(ErrorCode.VALIDATION, "文件编码无法识别，请另存为 UTF-8 的 CSV 或 .xlsx")
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]


def _header(cells: list[str]) -> tuple[dict[int, str], list[str]]:
    alias = {a: key for key, names in COLUMNS.items() for a in names}
    mapping: dict[int, str] = {}
    ignored: list[str] = []
    for i, raw in enumerate(cells):
        title = raw.replace("*", "").replace(" ", "").strip()
        key = alias.get(title)
        if key and key not in mapping.values():
            mapping[i] = key
        elif title:
            ignored.append(raw)
    if "name" not in mapping.values():
        raise BizError(
            ErrorCode.VALIDATION, "第一行要是表头，并且包含「客户名称」列（可以下载模板）"
        )
    return mapping, ignored


def _parse(filename: str, stream: BinaryIO) -> tuple[list[_Parsed], list[str], list[str]]:
    content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise BizError(ErrorCode.VALIDATION, "文件超过 2MB，请拆成几个文件导入")
    if not content.strip():
        raise BizError(ErrorCode.VALIDATION, "文件是空的")
    table = _read_table(filename, content)
    start = next((i for i, r in enumerate(table) if any(r)), None)
    if start is None:
        raise BizError(ErrorCode.VALIDATION, "文件是空的")
    mapping, ignored = _header(table[start])
    rows: list[_Parsed] = []
    for offset, cells in enumerate(table[start + 1 :], start=start + 2):
        if not any(cells):
            continue
        values = {key: cells[i] if i < len(cells) else "" for i, key in mapping.items()}
        rows.append(_Parsed(offset, values))
    if not rows:
        raise BizError(ErrorCode.VALIDATION, "表头下面没有数据")
    if len(rows) > MAX_ROWS:
        raise BizError(ErrorCode.VALIDATION, f"一次最多导入 {MAX_ROWS} 行，当前 {len(rows)} 行")
    return rows, list(mapping.values()), ignored


def _money(text: str) -> int | None:
    """「50000」「5万」「1,200.5」→ 分；不合法返回 -1。"""
    m = _MONEY.match(text.replace(",", "").replace("，", ""))
    if not m:
        return -1
    yuan = float(m.group(1)) * (10_000 if m.group(2) else 1)
    return round(yuan * 100)


def _check(p: _Parsed) -> None:
    v = p.values
    for key, limit in MAX_LEN.items():
        if len(v.get(key, "")) > limit:
            p.errors.append(f"{COLUMNS[key][0]}超过 {limit} 字")
    if not v.get("name"):
        p.errors.append("客户名称为空")
    elif len(core_name(v["name"])) < 2:
        p.errors.append("客户名称太短")
    level = v.get("level", "").upper()
    if level and level not in {"A", "B", "C"}:
        p.errors.append("等级只能填 A、B、C")
    if v.get("annual_budget") and _money(v["annual_budget"]) == -1:
        p.errors.append("年度预算要填数字（元），可以写「5万」")
    role = v.get("contact_role", "")
    if role and role not in _ROLE_BY_LABEL:
        p.errors.append(f"联系人角色只能填：{'、'.join(_ROLE_BY_LABEL)}")
    has_contact_detail = any(v.get(k) for k in ("contact_title", "contact_phone", "contact_role"))
    if has_contact_detail and not v.get("contact_name"):
        p.errors.append("填了联系人信息但没有联系人姓名")
    if v.get("contact_phone") and (err := phone_error(v["contact_phone"])):
        p.errors.append(err)
    if v.get("website") and normalize_website(v["website"]) is None:
        p.errors.append(WEBSITE_ERROR)


def _owners(db: Session, user: CurrentUser) -> dict[str, User]:
    """主管可以指定的负责人：本团队启用的成员，按姓名和账号都能找到。"""
    if user.role is not Role.MANAGER or user.team_id is None:
        return {}
    members = db.scalars(
        select(User).where(User.team_id == user.team_id, User.active.is_(True))
    ).all()
    out: dict[str, User] = {}
    for m in members:
        out[m.name] = m
        if m.username:
            out[m.username] = m
    return out


def _resolve_owner(p: _Parsed, user: CurrentUser, owners: dict[str, User]) -> Owner:
    text = p.values.get("owner", "")
    if not text or text == user.name:
        return "self"
    if user.role is not Role.MANAGER:
        p.errors.append("销售只能导入给自己（负责人列留空）")
        return "self"
    if text == POOL:
        return None
    hit = owners.get(text)
    if hit is None:
        p.errors.append(f"负责人「{text}」不是本团队的成员")
        return "self"
    return hit


def import_customers(
    db: Session, user: CurrentUser, filename: str, stream: BinaryIO, *, commit: bool
) -> ImportResult:
    ensure_business_writer(user)
    parsed, columns, ignored = _parse(filename, stream)
    owners = _owners(db, user)
    existing = list(db.scalars(select(Customer.name)))
    seen: dict[str, int] = {}  # 核心名 → 文件里第一次出现的行号
    rows: list[ImportRow] = []
    plan: list[tuple[_Parsed, User | str | None]] = []
    for p in parsed:
        _check(p)
        owner = _resolve_owner(p, user, owners)
        name = p.values.get("name", "")
        owner_name = user.name if owner == "self" else (owner.name if owner else None)
        if p.errors:
            rows.append(
                ImportRow(
                    line=p.line,
                    name=name,
                    owner_name=owner_name,
                    status="error",
                    message="；".join(p.errors),
                )
            )
            continue
        core = core_name(name)
        matches = similar_names(name, existing)
        same = [n for n, exact in matches if exact]
        if same:
            rows.append(
                ImportRow(
                    line=p.line,
                    name=name,
                    owner_name=owner_name,
                    status="duplicate",
                    message=f"客户已存在：{same[0]}",
                )
            )
            continue
        if core in seen:
            rows.append(
                ImportRow(
                    line=p.line,
                    name=name,
                    owner_name=owner_name,
                    status="duplicate",
                    message=f"与第 {seen[core]} 行重复",
                )
            )
            continue
        seen[core] = p.line
        similar = [n for n, _ in matches]
        if similar:
            p.warnings.append(f"名称相似：{'、'.join(similar[:3])}，确认不是同一家")
        rows.append(
            ImportRow(
                line=p.line, name=name, owner_name=owner_name, status="ok", warnings=p.warnings
            )
        )
        plan.append((p, owner))
    ok_count = len(plan)
    if commit and plan:
        _create(db, user, plan)
    return ImportResult(
        total=len(parsed),
        ok=ok_count,
        skipped=len(parsed) - ok_count,
        created=commit and ok_count > 0,
        columns=columns,
        ignored_columns=ignored,
        rows=rows,
    )


def _create(db: Session, user: CurrentUser, plan: list[tuple[_Parsed, Owner]]) -> None:
    assigned: Counter[uuid.UUID] = Counter()
    for p, owner in plan:
        v = p.values
        owner_id = user.id if owner == "self" else (owner.id if owner else None)
        team_id = owner.team_id if isinstance(owner, User) else user.team_id
        budget = _money(v["annual_budget"]) if v.get("annual_budget") else None
        tags = [t for t in _TAG_SPLIT.split(v.get("tags", "")) if t][:20]
        customer = Customer(
            name=v["name"].strip(),
            industry=v.get("industry") or None,
            level=(v.get("level") or "C").upper(),
            size=v.get("size") or None,
            address=v.get("address") or None,
            website=normalize_website(v["website"]) if v.get("website") else None,
            annual_budget=budget,
            tags=[t[:50] for t in tags],
            owner_id=owner_id,
            team_id=team_id,
        )
        db.add(customer)
        db.flush()
        if v.get("contact_name"):
            role = _ROLE_BY_LABEL.get(v.get("contact_role", ""))
            db.add(
                Contact(
                    customer_id=customer.id,
                    name=v["contact_name"],
                    title=v.get("contact_title") or None,
                    phone=v.get("contact_phone") or None,
                    role=role,
                    is_decision_maker=role == "decision_maker",
                    owner_id=owner_id,
                    team_id=team_id,
                )
            )
        where = "（公海）" if owner_id is None else ""
        activity_service.record(db, user, "customer", customer.id, "import", customer.name + where)
        if owner_id is not None and owner_id != user.id:
            assigned[owner_id] += 1
    db.flush()
    for uid, n in assigned.items():
        notification_service.notify(
            db,
            [uid],
            "customer_assigned",
            f"{user.name} 导入了 {n} 个客户给你",
            "在客户列表的「我负责的」里查看",
            "/customers",
        )
