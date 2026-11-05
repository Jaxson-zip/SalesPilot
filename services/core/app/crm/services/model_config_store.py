"""模型接入的底层：Key 加密、配置读写、推送网关、入参校验（model_config_service 的内部模块）。

- Key 用 MODEL_KEYS_SECRET 派生的密钥加密（Fernet）。没设置时退回 JWT_SECRET；
  设置之后旧密文仍能解开，下次保存时换成新密钥加密；
- 网关只把配置放在内存里，版本对不上（网关重启过）就重新推送。
"""

import base64
import copy
import hashlib
import ipaddress
import json
import logging
import re
import socket
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_configurer
from app.crm.models import Integration
from app.llm import client

logger = logging.getLogger(__name__)

KIND = "model_keys"
VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
ADAPTER_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_SLUG = re.compile(r"[^a-z0-9.]+")
GROUPS = ("chat-agent", "embed", "rerank")
# 变量名 → (厂商名, 在哪里申请)。models.yaml 新增厂商时在这里补一行，没补的按变量名显示
LABELS: dict[str, tuple[str, str]] = {
    "HUNYUAN_API_KEY": ("腾讯混元", "腾讯云控制台 → 混元大模型 → API Key 管理"),
    "DEEPSEEK_API_KEY": ("DeepSeek", "platform.deepseek.com → API keys"),
    "DASHSCOPE_API_KEY": ("通义千问（阿里云百炼）", "百炼控制台 → API-KEY"),
    "SILICONFLOW_API_KEY": ("硅基流动", "cloud.siliconflow.cn → API 密钥"),
}


# ---------- 加密 ----------


def _derive(secret: str) -> Fernet:
    digest = hashlib.sha256(b"salespilot-model-keys:" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet() -> MultiFernet:
    """第一个用于加密；后面的只用于解开旧密文（MODEL_KEYS_SECRET 设置之前用 JWT_SECRET 加密的）。"""
    settings = get_settings()
    keys = [_derive(settings.model_keys_secret)] if settings.model_keys_secret else []
    return MultiFernet([*keys, _derive(settings.jwt_secret)])


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def seal(key: str, user: CurrentUser) -> dict[str, Any]:
    return {
        "token": _fernet().encrypt(key.encode()).decode(),
        "tail": key[-4:] if len(key) >= 12 else None,  # 太短的 Key 露出末 4 位等于露出大半
        "by": user.name,
        "at": datetime.now(UTC).isoformat(),
    }


def _rotate(cfg: dict[str, Any]) -> None:
    """保存时把能解开的旧密文换成当前密钥加密。"""
    f = _fernet()
    for entry in [*cfg.get("keys", {}).values(), *cfg.get("custom", [])]:
        token = entry.get("token")
        if token and decrypt(token) is not None:
            entry["token"] = f.rotate(token.encode()).decode()


# ---------- 存储 ----------


def _row(db: Session, *, lock: bool = False) -> Integration | None:
    stmt = select(Integration).where(Integration.kind == KIND)
    return db.scalar(stmt.with_for_update() if lock else stmt)


def load(db: Session, *, lock: bool = False) -> dict[str, Any]:
    row = _row(db, lock=lock)
    return copy.deepcopy(dict(row.config or {})) if row else {}


def store(db: Session, user: CurrentUser | None, cfg: dict[str, Any]) -> None:
    _rotate(cfg)
    row = _row(db, lock=True)
    if row is None:
        row = Integration(kind=KIND, config={}, recent=[])
        db.add(row)
    row.config = cfg
    if user is not None:
        row.updated_by = user.name
    db.flush()


def _version(cfg: dict[str, Any]) -> str:
    """配置版本：密文、地址、分组任何一处变了版本就变；什么都没配时为空，和网关刚启动时一致。"""
    parts = {k: cfg.get(k) for k in ("keys", "builtin", "custom", "groups") if cfg.get(k)}
    if not parts:
        return ""
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def custom_alias(provider_id: str, model: str) -> str:
    """和网关 app/overlay.py 的 custom_alias 一致。"""
    return f"{provider_id}-{_SLUG.sub('-', model.lower()).strip('-')}"


# ---------- 推送网关 ----------


def _payload(cfg: dict[str, Any]) -> dict[str, Any]:
    keys = cfg.get("keys", {})
    overrides = cfg.get("builtin", {})
    builtin = {}
    for var in sorted(set(keys) | set(overrides)):
        ov = overrides.get(var, {})
        builtin[var] = {
            "key": decrypt(keys.get(var, {}).get("token")) or "",
            "base": ov.get("base", ""),
            "protocol": ov.get("protocol", ""),
            "adapter": ov.get("adapter", ""),
        }
    custom = [
        {
            "id": p["id"],
            "protocol": p["protocol"],
            "adapter": p.get("adapter", ""),
            "api_base": p.get("api_base", ""),
            "api_key": decrypt(p.get("token")) or "",
            "models": p["models"],
        }
        for p in cfg.get("custom", [])
    ]
    groups = {g: list(v) for g, v in cfg.get("groups", {}).items() if v}
    return {"version": _version(cfg), "builtin": builtin, "custom": custom, "groups": groups}


def _push(cfg: dict[str, Any]) -> dict[str, Any]:
    state = client.gateway_admin("PUT", "config", _payload(cfg))
    client.forget_availability()
    return state


def gateway_state(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """网关当前状态；版本对不上（网关重启过）就顺手重新推送。连不上返回 None。"""
    try:
        state = client.gateway_admin("GET", "config")
        if state.get("version", "") != _version(cfg):
            state = _push(cfg)
    except BizError:
        logger.warning("gateway unreachable when reading model config")
        return None
    return state


def push_quietly(cfg: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _push(cfg)
    except BizError:
        logger.warning("gateway unreachable, model config will be pushed by the sync loop")
        return None


# ---------- 校验 ----------


def require_admin(user: CurrentUser) -> None:
    ensure_configurer(user, "模型接入由系统管理员配置")


def invalid(message: str) -> BizError:
    return BizError(ErrorCode.VALIDATION, message)


# 无论是否允许内网都不能访问：云厂商元数据（AWS / GCP / Azure 的 169.254.169.254、
# 阿里云 100.100.100.200、AWS IPv6 fd00:ec2::254）、链路本地、组播、未指定地址
_METADATA_HOSTS = {
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("fd00:ec2::254"),
}


def allow_private() -> bool:
    return get_settings().model_allow_private_base is True


def always_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """云元数据、链路本地、组播、未指定地址：打开 MODEL_ALLOW_PRIVATE_BASE 也不允许。"""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip in _METADATA_HOSTS or ip.is_link_local or ip.is_multicast or ip.is_unspecified


def check_base(url: str) -> str:
    """接口地址：必须是 http(s)；正式模式下默认不允许解析到内网 / 本机 / 云厂商元数据地址。"""
    url = url.strip()
    if not url:
        return url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise invalid("接口地址要以 http:// 或 https:// 开头")
    private = allow_private()
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except (OSError, ValueError) as exc:
        if private:  # 允许内网时只拦元数据地址；内网域名可能只在模型服务器那边解析得了
            return url
        raise invalid(f"接口地址的域名解析不了：{parts.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if always_blocked(ip):
            raise invalid("接口地址指向云服务器元数据或链路本地地址，一律禁止")
        if not private and not ip.is_global:
            raise invalid(
                "接口地址指向内网或本机，正式环境默认禁止。"
                "自建模型请在服务器 .env 设置 MODEL_ALLOW_PRIVATE_BASE=true"
            )
    return url


def check_key(key: str) -> str:
    key = key.strip()
    if key and (len(key) < 4 or re.search(r"\s", key)):
        raise invalid("Key 格式不对：至少 4 位，不能有空格或换行")
    return key


def check_protocol(protocol: str, adapter: str) -> str:
    adapter = adapter.strip()
    if protocol == "native" and not ADAPTER_RE.match(adapter):
        raise invalid("原生协议要填写 LiteLLM 的适配名，例如 deepseek、dashscope、ollama")
    return adapter if protocol == "native" else ""
