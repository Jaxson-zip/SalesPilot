"""操作日志（企业审计）：记录、查询、导出权限、查看电话次数。

写入来源：
- 网页：AuditMiddleware 按「方法 + 路由」记录每个写请求（成功、失败、被拒都记）；
- AI：run_tool 执行写工具后记录（source=agent，detail 为工具摘要）；
- 敏感读：查看联系人完整电话、导出列表，由各自接口显式记录。

日志只增不改；记录失败只打日志，不影响业务请求。
"""

import logging
import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.crm.models import (
    AuditLog,
    Contact,
    Contract,
    Customer,
    Expense,
    Opportunity,
    Quote,
    Task,
)
from app.crm.schemas.common import Page, PageParams
from app.rules import load_rules
from app.rules.crm_calc import LOCAL_TZ

logger = logging.getLogger("core.audit")

# (方法, 路由模板) → (action, 中文名)。不在表里的写请求（试算、标记已读、AI 对话本身）不记录
ROUTES: dict[tuple[str, str], tuple[str, str]] = {
    ("POST", "/api/customers"): ("customer.create", "新建客户"),
    ("POST", "/api/customers/transfer"): ("customer.transfer", "转移客户"),
    ("POST", "/api/customers/{id}/release"): ("customer.release", "退回公海"),
    ("POST", "/api/customers/{id}/claim"): ("customer.claim", "领取客户"),
    ("PATCH", "/api/customers/{id}"): ("customer.update", "修改客户"),
    ("POST", "/api/customers/{id}/followups"): ("followup.create", "记录跟进"),
    ("POST", "/api/customers/{id}/contacts"): ("contact.create", "新增联系人"),
    ("PATCH", "/api/customers/{id}/contacts/{sub}"): ("contact.update", "修改联系人"),
    ("DELETE", "/api/customers/{id}/contacts/{sub}"): ("contact.delete", "删除联系人"),
    ("POST", "/api/opportunities"): ("opportunity.create", "新建商机"),
    ("PATCH", "/api/opportunities/{id}"): ("opportunity.update", "修改商机"),
    ("PATCH", "/api/opportunities/{id}/stage"): ("opportunity.stage", "推进商机阶段"),
    ("PUT", "/api/opportunities/{id}/meddic"): ("opportunity.meddic", "更新赢单要素"),
    ("PUT", "/api/opportunities/{id}/competitors"): ("opportunity.competitors", "标注竞争对手"),
    ("POST", "/api/competitors"): ("competitor.create", "新建竞品战卡"),
    ("PUT", "/api/competitors/{id}"): ("competitor.update", "修改竞品战卡"),
    ("DELETE", "/api/competitors/{id}"): ("competitor.delete", "删除竞品战卡"),
    ("PUT", "/api/reports/daily"): ("report.daily", "保存日报"),
    ("POST", "/api/reports/team/push"): ("report.push", "推送日报汇总到企业微信"),
    ("POST", "/api/reports/team/remind"): ("report.remind", "企业微信提醒未交日报"),
    ("PUT", "/api/integrations/wecom"): ("settings.wecom", "修改企业微信推送配置"),
    ("POST", "/api/integrations/wecom/test"): ("settings.wecom_test", "发送企业微信测试消息"),
    ("PATCH", "/api/quotes/{id}/items"): ("quote.items", "修改报价明细"),
    ("POST", "/api/quotes/{id}/submit"): ("quote.submit", "提交报价审批"),
    ("POST", "/api/quotes/{id}/send"): ("quote.send", "发送报价"),
    ("POST", "/api/quotes/{id}/accept"): ("quote.accept", "客户接受报价"),
    ("POST", "/api/quotes/{id}/reject"): ("quote.reject", "客户拒绝报价"),
    ("POST", "/api/contracts/{id}/payments"): ("payment.create", "登记回款"),
    ("PUT", "/api/contracts/{id}/payment-plan"): ("payment.plan", "调整回款计划"),
    ("POST", "/api/expenses"): ("expense.create", "新建报销"),
    ("POST", "/api/expenses/{id}/submit"): ("expense.submit", "提交报销"),
    ("POST", "/api/expenses/{id}/attachments"): ("attachment.upload", "上传票据"),
    ("DELETE", "/api/attachments/{id}"): ("attachment.delete", "删除票据"),
    ("POST", "/api/approvals/{id}/decide"): ("approval.decide", "审批"),
    ("PUT", "/api/product-lines/{id}"): ("product_line.update", "修改产品线"),
    ("PUT", "/api/settings/rules"): ("settings.rules", "修改业务规则"),
    ("PUT", "/api/packs/{id}/settings"): ("pack.settings", "修改行业包规则"),
    ("PUT", "/api/packs/{id}/catalog/{sub}"): ("pack.catalog", "修改产品价格"),
    ("DELETE", "/api/packs/{id}/catalog/{sub}"): ("pack.catalog_reset", "恢复产品价格"),
    ("POST", "/api/packs/{id}/knowledge"): ("pack.knowledge_upload", "上传知识库文档"),
    ("DELETE", "/api/packs/{id}/knowledge/{sub}"): ("pack.knowledge_delete", "删除知识库文档"),
    ("POST", "/api/tasks"): ("task.create", "新建任务"),
    ("PATCH", "/api/tasks/{id}"): ("task.update", "修改任务"),
    ("DELETE", "/api/tasks/{id}"): ("task.delete", "删除任务"),
    ("DELETE", "/api/agent/threads/{id}"): ("thread.delete", "删除 AI 会话"),
}

# AI 写工具 → (action, 中文名)
TOOL_ACTIONS: dict[str, tuple[str, str]] = {
    "add_followup": ("followup.create", "记录跟进"),
    "digest_material": ("material.digest", "整理材料写入"),
    "update_opportunity_stage": ("opportunity.stage", "推进商机阶段"),
    "create_task": ("task.create", "新建任务"),
    "submit_expense": ("expense.create", "新建报销"),
    "generate_quote": ("quote.create", "生成报价单"),
    "decide_approval": ("approval.decide", "审批"),
}

PHONE_REVEAL = ("contact.phone_view", "查看联系人电话")
LOGIN = ("auth.login", "登录")
EXPORT_LABELS = {
    "customers": "客户",
    "opportunities": "商机",
    "quotes": "报价单",
    "contracts": "合同",
    "expenses": "报销",
}
ExportEntity = Literal["customers", "opportunities", "quotes", "contracts", "expenses"]

_PARAM = re.compile(r"\{(id|sub)\}")
_COMPILED = [
    (method, re.compile("^" + _PARAM.sub(r"(?P<\1>[^/]+)", tpl) + "$"), action)
    for (method, tpl), action in ROUTES.items()
]


def match_route(method: str, path: str) -> tuple[str, str, str | None] | None:
    """返回 (action, label, target_id)；不需要记录的请求返回 None。"""
    for m, pattern, (action, label) in _COMPILED:
        if m != method:
            continue
        hit = pattern.match(path)
        if hit:
            groups = hit.groupdict()
            return action, label, groups.get("sub") or groups.get("id")
    return None


class AuditEntry(BaseModel):
    action: str
    label: str
    source: Literal["web", "agent"] = "web"
    method: str | None = None
    path: str | None = None
    target_id: str | None = None
    status: int = 200
    ok: bool = True
    detail: str | None = None
    extra: dict[str, Any] | None = None
    ip: str | None = None
    request_id: str | None = None


def write(db: Session, user: CurrentUser | None, entry: AuditEntry) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            user_name=user.name if user else None,
            role=user.role.value if user else None,
            team_id=user.team_id if user else None,
            **entry.model_dump(),
        )
    )
    db.flush()


def record(user: CurrentUser | None, entry: AuditEntry) -> None:
    """独立事务写一条日志；失败只记录错误，不影响调用方。"""
    try:
        with session_scope() as db:
            write(db, user, entry)
    except Exception:
        logger.exception("audit write failed: %s", entry.action)


# ---------- 查询 ----------


class AuditItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    user_name: str | None
    role: str | None
    action: str
    label: str
    source: str
    target_id: str | None
    status: int
    ok: bool
    detail: str | None
    ip: str | None
    target_name: str | None = None  # 对象名称（客户名、单号、联系人…），已删除的对象为空


class AuditFilter(BaseModel):
    q: str | None = None
    action: str | None = None
    user_id: uuid.UUID | None = None
    ok: bool | None = None
    source: Literal["web", "agent"] | None = None
    date_from: date | None = None
    date_to: date | None = None


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=LOCAL_TZ)


def list_logs(
    db: Session, user: CurrentUser, f: AuditFilter, params: PageParams
) -> Page[AuditItem]:
    """管理员看全公司，主管看本团队；销售无权查看。"""
    if user.role == Role.SALES:
        raise BizError(ErrorCode.FORBIDDEN, "操作日志仅主管和管理员可以查看")
    stmt = select(AuditLog)
    if user.role == Role.MANAGER:
        stmt = stmt.where(AuditLog.team_id == user.team_id)
    if f.action:
        stmt = stmt.where(AuditLog.action.startswith(f.action))
    if f.user_id:
        stmt = stmt.where(AuditLog.user_id == f.user_id)
    if f.ok is not None:
        stmt = stmt.where(AuditLog.ok == f.ok)
    if f.source:
        stmt = stmt.where(AuditLog.source == f.source)
    if f.date_from:
        stmt = stmt.where(AuditLog.created_at >= _day_start(f.date_from))
    if f.date_to:
        stmt = stmt.where(AuditLog.created_at < _day_start(f.date_to + timedelta(days=1)))
    if f.q:
        kw = f"%{f.q.strip()}%"
        stmt = stmt.where(
            or_(
                AuditLog.user_name.ilike(kw),
                AuditLog.label.ilike(kw),
                AuditLog.detail.ilike(kw),
                AuditLog.target_id.ilike(kw),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    items = [AuditItem.model_validate(r, from_attributes=True) for r in rows]
    names = target_names(db, [i.target_id for i in items])
    for i in items:
        i.target_name = names.get(i.target_id or "")
    return Page[AuditItem](items=items, total=total)


_NAMED: list[tuple[Any, Any]] = [
    (Customer, Customer.name),
    (Opportunity, Opportunity.name),
    (Quote, Quote.code),
    (Contract, Contract.code),
    (Expense, Expense.code),
    (Contact, Contact.name),
    (Task, Task.title),
]


def target_names(db: Session, ids: list[str | None]) -> dict[str, str]:
    """按 id 批量查对象名称（日志里存的是 id，展示时换成名称）。"""
    uuids: set[uuid.UUID] = set()
    for raw in ids:
        try:
            uuids.add(uuid.UUID(str(raw)))
        except ValueError:
            continue
    out: dict[str, str] = {}
    if not uuids:
        return out
    for model, col in _NAMED:
        for oid, name in db.execute(select(model.id, col).where(model.id.in_(uuids))):
            out[str(oid)] = name
    return out


# ---------- 敏感操作 ----------


def count_today(db: Session, user: CurrentUser, action: str) -> int:
    start = _day_start(datetime.now(LOCAL_TZ).date())
    stmt = select(func.count(AuditLog.id)).where(
        AuditLog.user_id == user.id,
        AuditLog.action == action,
        AuditLog.ok.is_(True),
        AuditLog.created_at >= start,
    )
    return db.scalar(stmt) or 0


class ExportIn(BaseModel):
    entity: ExportEntity
    rows: int


class ExportOut(BaseModel):
    allowed: bool
    max_rows: int


def check_export(db: Session, user: CurrentUser, body: ExportIn, ip: str | None) -> ExportOut:
    """导出前登记：角色无权导出该数据、或超过单次条数上限时拒绝（被拒也记一条）。"""
    privacy = load_rules().privacy
    label = EXPORT_LABELS[body.entity]
    roles = privacy.export_roles.get(body.entity, [])
    entry = AuditEntry(
        action=f"export.{body.entity}",
        label=f"导出{label}",
        detail=f"{body.rows} 条",
        extra={"rows": body.rows},
        ip=ip,
    )
    reason = None
    if user.role.value not in roles:
        reason = f"当前角色不能导出{label}，请联系主管"
    elif body.rows > privacy.export_max_rows:
        reason = f"单次最多导出 {privacy.export_max_rows} 条，请先筛选"
    if reason:
        record(user, entry.model_copy(update={"ok": False, "status": 403, "detail": reason}))
        raise BizError(ErrorCode.FORBIDDEN, reason, {"rule": "privacy"})
    write(db, user, entry)
    return ExportOut(allowed=True, max_rows=privacy.export_max_rows)
