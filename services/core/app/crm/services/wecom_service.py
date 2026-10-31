"""企业微信群机器人推送（Webhook）。

- 地址只接受企业微信官方 webhook（防止被当成任意地址请求的跳板），网页上只显示脱敏后的 key；
  环境变量 WECOM_WEBHOOK_URL 作为默认值，网页上保存的地址优先。
- 业务代码调用 queue() 把消息挂在当前数据库会话上，事务提交后才在后台线程发送，
  回滚则丢弃——不会推送一条实际没有保存成功的审批或喜报，也不拖慢接口响应。
- 发送结果记在 integrations.recent（最近 20 条），管理员页面可见。
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.config import get_settings
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_configurer
from app.crm.models import Integration

logger = logging.getLogger(__name__)

KIND = "wecom"
URL_RE = re.compile(
    r"^https://qyapi\.weixin\.qq\.com/cgi-bin/webhook/send\?key=[A-Za-z0-9-]{8,64}$"
)
MAX_BYTES = 4000  # 企业微信 markdown 内容上限 4096 字节
RECENT = 20
QUEUE_KEY = "wecom_queue"

Event = Literal[
    "approval_pending",
    "deal_won",
    "report_summary",
    "report_remind",
    "report_remind_auto",
    "payment_overdue",
]
EVENTS: dict[str, str] = {
    "approval_pending": "新的待审批（报价 / 报销超出权限）",
    "deal_won": "赢单喜报",
    "report_summary": "主管推送团队日报汇总",
    "report_remind": "主管提醒未提交日报",
    "report_remind_auto": "定时任务：工作日自动催交日报",
    "payment_overdue": "定时任务：回款逾期",
}
# 定时任务自动发的消息不默认开启：管理员在「消息推送」里勾选后才推到群
AUTO_EVENTS = {"report_remind_auto", "payment_overdue"}
DEFAULT_EVENTS = [e for e in EVENTS if e not in AUTO_EVENTS]

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="wecom")


class WecomEventOption(BaseModel):
    key: str
    label: str


class WecomPush(BaseModel):
    at: datetime
    event: str
    title: str
    ok: bool
    error: str | None = None


class WecomConfigOut(BaseModel):
    configured: bool
    source: Literal["web", "env", "none"]
    webhook_masked: str | None = None
    enabled: bool
    events: list[str]
    options: list[WecomEventOption]
    recent: list[WecomPush]
    web_base_url: str


class WecomConfigIn(BaseModel):
    # None 表示不修改地址；空字符串表示清除网页上保存的地址（回到环境变量）
    webhook_url: str | None = Field(default=None, max_length=300)
    enabled: bool = True
    events: list[str] = Field(default_factory=lambda: list(DEFAULT_EVENTS))


class PushIn(BaseModel):
    content: str = Field(min_length=1, max_length=3000)


class PushOut(BaseModel):
    ok: bool
    error: str | None = None


def mask(url: str) -> str:
    key = url.split("key=", 1)[-1]
    return f"…key={key[:4]}****{key[-4:]}" if len(key) > 8 else "…key=****"


def _row(db: Session) -> Integration | None:
    return db.scalar(select(Integration).where(Integration.kind == KIND))


def _resolve(row: Integration | None) -> tuple[str | None, Literal["web", "env", "none"]]:
    url = (row.config or {}).get("webhook_url") if row else None
    if url:
        return url, "web"
    env = get_settings().wecom_webhook_url
    if env and URL_RE.match(env):
        return env, "env"
    return None, "none"


def _require_admin(user: CurrentUser) -> None:
    ensure_configurer(user, "企业微信推送由系统管理员配置")


def get_config(db: Session, user: CurrentUser) -> WecomConfigOut:
    _require_admin(user)
    row = _row(db)
    url, source = _resolve(row)
    cfg = row.config if row else {}
    return WecomConfigOut(
        configured=url is not None,
        source=source,
        webhook_masked=mask(url) if url else None,
        enabled=bool(cfg.get("enabled", True)),
        events=list(cfg.get("events", DEFAULT_EVENTS)),
        options=[WecomEventOption(key=k, label=v) for k, v in EVENTS.items()],
        recent=[WecomPush.model_validate(r) for r in (row.recent if row else [])],
        web_base_url=get_settings().web_base_url,
    )


def save_config(db: Session, user: CurrentUser, body: WecomConfigIn) -> WecomConfigOut:
    _require_admin(user)
    row = _row(db)
    if row is None:
        row = Integration(kind=KIND, config={}, recent=[])
        db.add(row)
    cfg = dict(row.config or {})
    if body.webhook_url is not None:
        url = body.webhook_url.strip()
        if url and not URL_RE.match(url):
            raise BizError(
                ErrorCode.VALIDATION,
                "请粘贴企业微信群机器人的 Webhook 地址"
                "（https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…）",
            )
        cfg["webhook_url"] = url or None
    cfg["enabled"] = body.enabled
    cfg["events"] = [e for e in body.events if e in EVENTS]
    row.config = cfg
    row.updated_by = user.name
    db.flush()
    return get_config(db, user)


def _cut(text: str) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= MAX_BYTES:
        return text
    return raw[: MAX_BYTES - 6].decode("utf-8", errors="ignore") + "\n……"


def send(url: str, content: str, timeout: float = 5) -> PushOut:
    """同步发送一条 markdown 消息。企业微信返回 HTTP 200 + errcode 表示结果。"""
    try:
        r = httpx.post(
            url,
            json={"msgtype": "markdown", "markdown": {"content": _cut(content)}},
            timeout=timeout,
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200 and data.get("errcode") == 0:
            return PushOut(ok=True)
        return PushOut(ok=False, error=f"企业微信返回：{data.get('errmsg') or r.status_code}")
    except httpx.HTTPError as exc:
        return PushOut(ok=False, error=f"连接企业微信失败：{type(exc).__name__}")


def _record(event_name: str, title: str, out: PushOut) -> None:
    try:
        with session_scope() as db:
            row = _row(db)
            if row is None:
                row = Integration(kind=KIND, config={}, recent=[])
                db.add(row)
            item = WecomPush(
                at=datetime.now(UTC), event=event_name, title=title, ok=out.ok, error=out.error
            ).model_dump(mode="json")
            row.recent = [item, *(row.recent or [])][:RECENT]
    except Exception:
        logger.warning("wecom: failed to record push result", exc_info=True)


def _deliver(url: str, event_name: str, title: str, content: str) -> PushOut:
    out = send(url, content)
    if not out.ok:
        logger.warning("wecom push failed: %s %s", event_name, out.error)
    _record(event_name, title, out)
    return out


def enabled_url(db: Session, event_name: str) -> str | None:
    row = _row(db)
    url, _ = _resolve(row)
    cfg = row.config if row else {}
    if url is None or not cfg.get("enabled", True):
        return None
    if event_name not in cfg.get("events", DEFAULT_EVENTS):
        return None
    return url


def queue(db: Session, event_name: Event, title: str, content: str) -> None:
    """事务提交后推送（未配置或该事件关闭时什么都不做）。"""
    url = enabled_url(db, event_name)
    if url is None:
        return
    db.info.setdefault(QUEUE_KEY, []).append((url, event_name, title, content))


@event.listens_for(Session, "after_commit")
def _flush_queue(session: Session) -> None:
    for item in session.info.pop(QUEUE_KEY, []):
        _pool.submit(_deliver, *item)


@event.listens_for(Session, "after_rollback")
def _drop_queue(session: Session) -> None:
    session.info.pop(QUEUE_KEY, None)


def link(path: str, text: str) -> str:
    return f"[{text}]({get_settings().web_base_url.rstrip('/')}{path})"


def send_test(db: Session, user: CurrentUser) -> PushOut:
    _require_admin(user)
    url, _ = _resolve(_row(db))
    if url is None:
        raise BizError(ErrorCode.VALIDATION, "还没有配置 Webhook 地址")
    content = (
        f"**SalesPilot 测试消息**\n> 由 {user.name} 在系统设置中发送，收到说明群机器人配置正确。"
    )
    return _deliver(url, "test", "测试消息", content)


def push_now(
    db: Session, user: CurrentUser, event_name: Event, title: str, content: str
) -> PushOut:
    """主管手动推送（日报汇总、提醒），同步返回结果。"""
    if user.role == Role.SALES:
        raise BizError(ErrorCode.FORBIDDEN, "只有主管和管理员可以推送到群")
    url = enabled_url(db, event_name)
    if url is None:
        raise BizError(
            ErrorCode.VALIDATION, "企业微信推送未开启：请管理员在「系统设置 → 消息推送」配置"
        )
    return _deliver(url, event_name, title, content)


def config_flags(db: Session) -> dict[str, Any]:
    """非管理员也能看到的开关状态（决定是否显示「推送到群」按钮），不含地址。"""
    row = _row(db)
    url, _ = _resolve(row)
    cfg = row.config if row else {}
    on = url is not None and bool(cfg.get("enabled", True))
    events = cfg.get("events", DEFAULT_EVENTS)
    return {e: on and e in events for e in EVENTS}
