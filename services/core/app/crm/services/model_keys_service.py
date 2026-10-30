"""模型厂商 Key：管理员在网页上填写，加密存库，推送给网关立即生效。

- 网页上保存的优先，没填的厂商继续用 .env（与企业微信推送地址同样的规则）；
- 用 JWT_SECRET 派生的密钥加密（Fernet）。换了 JWT_SECRET 之后旧 Key 解不开，页面提示重新填写；
- 网页上只显示末 4 位，任何接口都不返回完整 Key；操作日志不记请求体；
- 网关只把 Key 放在内存里：core 启动时和之后每分钟比对一次版本，网关重启过就重新推送。
"""

import base64
import hashlib
import json
import logging
import re
import threading
from datetime import UTC, datetime
from typing import Any, Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.config import get_settings
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.crm.models import Integration
from app.llm import client

logger = logging.getLogger(__name__)

KIND = "model_keys"
SYNC_SECONDS = 60
VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
# 变量名 → (厂商名, 在哪里申请)。models.yaml 新增厂商时在这里补一行，没补的按变量名显示
LABELS: dict[str, tuple[str, str]] = {
    "HUNYUAN_API_KEY": ("腾讯混元", "腾讯云控制台 → 混元大模型 → API Key 管理"),
    "DEEPSEEK_API_KEY": ("DeepSeek", "platform.deepseek.com → API keys"),
    "DASHSCOPE_API_KEY": ("通义千问（阿里云百炼）", "百炼控制台 → API-KEY"),
}


class ProviderKey(BaseModel):
    var: str
    label: str
    hint: str
    models: list[str]
    # web：网页上保存的；env：服务器 .env；none：都没有
    source: Literal["web", "env", "none"]
    tail: str | None = None
    saved_by: str | None = None
    saved_at: datetime | None = None
    # 网页上存过，但 JWT_SECRET 换过、解不开了
    broken: bool = False
    # 网关里用这个 Key 的模型是否有可用的；网关连不上时为 None
    available: bool | None = None


class ModelKeysOut(BaseModel):
    gateway_ok: bool
    providers: list[ProviderKey]


class ModelKeyIn(BaseModel):
    var: str = Field(min_length=1, max_length=64)
    # 空字符串 = 删除网页上保存的 Key（回到 .env）
    key: str = Field(max_length=500)


class KeyTestIn(BaseModel):
    var: str = Field(min_length=1, max_length=64)
    # 不填 = 测当前生效的 Key
    key: str | None = Field(default=None, max_length=500)


class KeyTestOut(BaseModel):
    ok: bool
    model: str | None = None
    error: str | None = None


def _require_admin(user: CurrentUser) -> None:
    if user.role != Role.ADMIN:
        raise BizError(ErrorCode.FORBIDDEN, "模型 Key 由系统管理员配置", {"rule": "role_forbidden"})


def _fernet() -> Fernet:
    digest = hashlib.sha256(b"salespilot-model-keys:" + get_settings().jwt_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def _row(db: Session) -> Integration | None:
    return db.scalar(select(Integration).where(Integration.kind == KIND))


def _saved(db: Session) -> dict[str, dict[str, Any]]:
    row = _row(db)
    return dict((row.config or {}).get("keys", {})) if row else {}


def _version(saved: dict[str, dict[str, Any]]) -> str:
    """配置版本：密文变了版本就变；没有网页上的 Key 时为空，和网关刚启动时一致。"""
    if not saved:
        return ""
    tokens = {var: entry["token"] for var, entry in saved.items()}
    return hashlib.sha256(json.dumps(tokens, sort_keys=True).encode()).hexdigest()[:16]


def _plain(saved: dict[str, dict[str, Any]]) -> dict[str, str]:
    out = {}
    for var, entry in saved.items():
        key = _decrypt(entry["token"])
        if key:
            out[var] = key
    return out


def _push(saved: dict[str, dict[str, Any]]) -> dict[str, Any]:
    state = client.gateway_admin("PUT", "keys", {"keys": _plain(saved), "version": _version(saved)})
    client.forget_availability()
    return state


def _gateway_state(saved: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """网关当前状态；版本对不上（网关重启过）就顺手重新推送。连不上返回 None。"""
    try:
        state = client.gateway_admin("GET", "providers")
        if state.get("version", "") != _version(saved):
            state = _push(saved)
    except BizError:
        logger.warning("gateway unreachable when reading provider keys")
        return None
    return state


def _provider(var: str, entry: dict[str, Any] | None, card: dict[str, Any] | None) -> ProviderKey:
    label, hint = LABELS.get(var, (var, "按厂商文档申请"))
    broken = entry is not None and _decrypt(entry["token"]) is None
    if entry is not None and not broken:
        source: Literal["web", "env", "none"] = "web"
    elif card and card.get("env_configured"):
        source = "env"
    else:
        source = "none"
    return ProviderKey(
        var=var,
        label=label,
        hint=hint,
        models=list(card.get("models", [])) if card else [],
        source=source,
        tail=entry.get("tail") if entry else None,
        saved_by=entry.get("by") if entry else None,
        saved_at=datetime.fromisoformat(entry["at"]) if entry else None,
        broken=broken,
        available=bool(card.get("available")) if card else None,
    )


def _status(saved: dict[str, dict[str, Any]], state: dict[str, Any] | None) -> ModelKeysOut:
    cards = {p["var"]: p for p in (state or {}).get("providers", [])}
    names = list(cards) if state is not None else list(LABELS)
    names += [v for v in saved if v not in names]
    providers = [_provider(v, saved.get(v), cards.get(v)) for v in names]
    return ModelKeysOut(gateway_ok=state is not None, providers=providers)


def get_status(db: Session, user: CurrentUser) -> ModelKeysOut:
    _require_admin(user)
    saved = _saved(db)
    return _status(saved, _gateway_state(saved))


def save_key(db: Session, user: CurrentUser, body: ModelKeyIn) -> ModelKeysOut:
    """保存（或清除）一个厂商的 Key，并推送给网关。网关暂时连不上也先存下，恢复后自动推送。"""
    _require_admin(user)
    var, key = body.var.strip(), body.key.strip()
    if not VAR_RE.match(var):
        raise BizError(ErrorCode.VALIDATION, "厂商变量名不正确")
    state = _gateway_state(_saved(db))
    if state is not None and var not in {p["var"] for p in state.get("providers", [])}:
        raise BizError(ErrorCode.VALIDATION, f"网关的模型清单里没有用到 {var}")
    if key and (len(key) < 8 or re.search(r"\s", key)):
        raise BizError(ErrorCode.VALIDATION, "Key 格式不对：至少 8 位，不能有空格或换行")
    row = _row(db)
    if row is None:
        row = Integration(kind=KIND, config={}, recent=[])
        db.add(row)
    saved = dict((row.config or {}).get("keys", {}))
    if key:
        saved[var] = {
            "token": _fernet().encrypt(key.encode()).decode(),
            "tail": key[-4:],
            "by": user.name,
            "at": datetime.now(UTC).isoformat(),
        }
    else:
        saved.pop(var, None)
    row.config = {**(row.config or {}), "keys": saved}
    row.updated_by = user.name
    db.flush()
    try:
        state = _push(saved)
    except BizError:
        logger.warning("gateway unreachable, provider keys will be pushed by the sync loop")
        state = None
    return _status(saved, state)


def test_key(db: Session, user: CurrentUser, body: KeyTestIn) -> KeyTestOut:
    """用填写的 Key（或当前生效的 Key）发一次最小请求，不保存。"""
    _require_admin(user)
    key = (body.key or "").strip() or None
    if key is None:
        entry = _saved(db).get(body.var)
        key = _decrypt(entry["token"]) if entry else None  # 没有网页上的：网关用 .env 的
    try:
        result = client.gateway_admin("POST", "keys/test", {"var": body.var, "key": key})
    except BizError as exc:
        return KeyTestOut(ok=False, error=f"连不上模型网关：{exc.message}")
    return KeyTestOut.model_validate(result)


# ---------- 后台同步 ----------


def sync_once() -> None:
    with session_scope() as db:
        saved = _saved(db)
    _gateway_state(saved)


def start_sync() -> threading.Event:
    """后台每分钟比对一次：网关单独重启后丢了网页上的 Key，由这里补推。返回停止信号。"""
    stop = threading.Event()

    def loop() -> None:
        while True:
            try:
                sync_once()
            except Exception:
                logger.exception("provider key sync failed")
            if stop.wait(SYNC_SECONDS):
                return

    threading.Thread(target=loop, name="model-key-sync", daemon=True).start()
    return stop
