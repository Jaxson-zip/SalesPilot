"""模型接入：管理员在网页上配置厂商与默认模型，加密存库，推给网关立即生效。

- 内置厂商（models.yaml 里的混元、DeepSeek、通义）：可以改 Key、接口地址、协议；
  网页上填的优先，没填的用 .env；
- 自定义厂商：任意 OpenAI 兼容接口或 LiteLLM 原生适配（Kimi、智谱、自建 vLLM / Ollama 等）；
- 默认模型：对话（chat-agent）、重排（rerank）的主用和备用顺序；知识库向量（embed）单独切换，见下；
- Key 用 MODEL_KEYS_SECRET 派生的密钥加密（Fernet）。没设置时退回 JWT_SECRET；
  设置之后旧密文仍能解开，下次保存时换成新密钥加密。两个都换掉之后旧 Key 解不开，页面提示重新填写；
- 网页上只显示末 4 位，任何接口都不返回完整 Key；操作日志不记请求体；
- 接口地址在正式模式下默认不允许指向内网或本机（防止借服务器访问内网），自建模型需在 .env 打开
  MODEL_ALLOW_PRIVATE_BASE；
- 换知识库向量模型：后台用新模型把全部知识块重新向量化，全部成功后一次性写入并切换，
  失败不影响现有检索；
- 网关只把配置放在内存里：core 启动时和之后每分钟比对一次版本，网关重启过就重新推送。
"""

import base64
import copy
import hashlib
import ipaddress
import json
import logging
import re
import socket
import threading
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.config import get_settings
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.common.permissions import ensure_configurer
from app.crm.models import Integration, KbChunk
from app.llm import client
from app.rag.chunking import Chunk, embedding_text
from app.rag.ingest import EMBED_BATCH

logger = logging.getLogger(__name__)

KIND = "model_keys"
SYNC_SECONDS = 60
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
}

Kind = Literal["chat", "embedding", "rerank"]
LinkType = Literal["openai_compat", "native"]
ProtocolChoice = Literal["", "openai_compat", "native"]


# ---------- 出参 ----------


class ModelCard(BaseModel):
    alias: str
    model: str
    link: str
    kind: Kind
    tools: bool = False
    dims: int | None = None
    available: bool
    unavailable_reason: str | None = None
    provider: str  # 厂商名（显示用）


class BuiltinOut(BaseModel):
    var: str
    label: str
    hint: str
    # web：网页上保存的；env：服务器 .env；none：都没有
    key_source: Literal["web", "env", "none"]
    tail: str | None = None
    saved_by: str | None = None
    saved_at: datetime | None = None
    # 网页上存过，但加密密钥换过、解不开了
    broken: bool = False
    base: str = ""  # 网页上改的接口地址；空 = 默认
    default_base: str = ""
    protocol: ProtocolChoice = ""  # 空 = 按模型清单（已通过契约测试）
    adapter: str = ""
    # 网关里这家的模型是否有可用的；网关连不上时为 None
    available: bool | None = None
    models: list[ModelCard] = []


class Capabilities(BaseModel):
    """自定义模型的能力：测试连接时自动检测，也可以手动改。"""

    tools: bool = False
    stream: bool = True
    stream_tools: bool = False
    json_mode: bool = False
    dims: int | None = Field(default=None, ge=1, le=8192)


class CustomModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    kind: Kind = "chat"
    capabilities: Capabilities = Field(default_factory=Capabilities)


class CustomModelOut(CustomModelIn):
    alias: str
    available: bool | None = None
    unavailable_reason: str | None = None


class CustomOut(BaseModel):
    id: str
    name: str
    protocol: LinkType
    adapter: str = ""
    api_base: str = ""
    tail: str | None = None
    has_key: bool = False
    broken: bool = False
    saved_by: str | None = None
    saved_at: datetime | None = None
    available: bool | None = None
    models: list[CustomModelOut]


class ReindexOut(BaseModel):
    status: Literal["idle", "running", "done", "failed"] = "idle"
    target: str | None = None
    done: int = 0
    total: int = 0
    error: str | None = None
    by: str | None = None
    at: datetime | None = None


class ModelConfigOut(BaseModel):
    gateway_ok: bool
    builtin: list[BuiltinOut]
    custom: list[CustomOut]
    # 当前生效的分组（chat-agent / embed / rerank → 模型别名，按顺序）和 models.yaml 的默认
    groups: dict[str, list[str]]
    group_defaults: dict[str, list[str]]
    models: list[ModelCard]
    embedding_dims: int
    kb_chunks: int
    reindex: ReindexOut
    allow_private_base: bool


class TestOut(BaseModel):
    ok: bool
    model: str | None = None
    error: str | None = None
    dims: int | None = None  # Embedding 模型的向量维度
    capabilities: dict[str, bool] | None = None  # 对话模型检测到的能力


# ---------- 入参 ----------


class BuiltinIn(BaseModel):
    var: str = Field(min_length=1, max_length=64)
    # None = 不改；空字符串 = 删除网页上保存的 Key（回到 .env）
    key: str | None = Field(default=None, max_length=500)
    base: str = Field(default="", max_length=500)
    protocol: ProtocolChoice = ""
    adapter: str = Field(default="", max_length=32)


class BuiltinTestIn(BuiltinIn):
    """表单上的值；key 不填 = 测当前生效的 Key。"""


class CustomIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    protocol: LinkType = "openai_compat"
    adapter: str = Field(default="", max_length=32)
    api_base: str = Field(default="", max_length=500)
    # None = 不改；空字符串 = 删除
    key: str | None = Field(default=None, max_length=500)
    models: list[CustomModelIn] = Field(min_length=1, max_length=20)


class CustomTestIn(BaseModel):
    protocol: LinkType = "openai_compat"
    adapter: str = Field(default="", max_length=32)
    api_base: str = Field(default="", max_length=500)
    key: str | None = Field(default=None, max_length=500)  # 不填 = 用这个厂商已保存的
    model: CustomModelIn
    detect: bool = True


class GroupsIn(BaseModel):
    chat: list[str] = Field(min_length=1, max_length=10)
    rerank: list[str] = Field(default_factory=list, max_length=10)


class EmbeddingIn(BaseModel):
    alias: str = Field(min_length=1, max_length=160)


# ---------- 加密与存储 ----------


def _derive(secret: str) -> Fernet:
    digest = hashlib.sha256(b"salespilot-model-keys:" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet() -> MultiFernet:
    """第一个用于加密；后面的只用于解开旧密文（MODEL_KEYS_SECRET 设置之前用 JWT_SECRET 加密的）。"""
    settings = get_settings()
    keys = [_derive(settings.model_keys_secret)] if settings.model_keys_secret else []
    return MultiFernet([*keys, _derive(settings.jwt_secret)])


def _decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def _seal(key: str, user: CurrentUser) -> dict[str, Any]:
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
        if token and _decrypt(token) is not None:
            entry["token"] = f.rotate(token.encode()).decode()


def _row(db: Session, *, lock: bool = False) -> Integration | None:
    stmt = select(Integration).where(Integration.kind == KIND)
    return db.scalar(stmt.with_for_update() if lock else stmt)


def _load(db: Session, *, lock: bool = False) -> dict[str, Any]:
    row = _row(db, lock=lock)
    return copy.deepcopy(dict(row.config or {})) if row else {}


def _store(db: Session, user: CurrentUser | None, cfg: dict[str, Any]) -> None:
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
            "key": _decrypt(keys.get(var, {}).get("token")) or "",
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
            "api_key": _decrypt(p.get("token")) or "",
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


def _gateway_state(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """网关当前状态；版本对不上（网关重启过）就顺手重新推送。连不上返回 None。"""
    try:
        state = client.gateway_admin("GET", "config")
        if state.get("version", "") != _version(cfg):
            state = _push(cfg)
    except BizError:
        logger.warning("gateway unreachable when reading model config")
        return None
    return state


def _push_quietly(cfg: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _push(cfg)
    except BizError:
        logger.warning("gateway unreachable, model config will be pushed by the sync loop")
        return None


# ---------- 状态 ----------

# 进行中的向量重建（只在本进程内）：target, done, total, by, at
_JOB: dict[str, Any] = {}
_JOB_LOCK = threading.Lock()


def _builtin_out(var: str, cfg: dict[str, Any], card: dict[str, Any] | None) -> BuiltinOut:
    label, hint = LABELS.get(var, (var, "按厂商文档申请"))
    entry = cfg.get("keys", {}).get(var)
    broken = entry is not None and _decrypt(entry["token"]) is None
    if entry is not None and not broken:
        source: Literal["web", "env", "none"] = "web"
    elif card and card.get("env_configured"):
        source = "env"
    else:
        source = "none"
    ov = cfg.get("builtin", {}).get(var, {})
    return BuiltinOut(
        var=var,
        label=label,
        hint=hint,
        key_source=source,
        tail=entry.get("tail") if entry else None,
        saved_by=entry.get("by") if entry else None,
        saved_at=datetime.fromisoformat(entry["at"]) if entry else None,
        broken=broken,
        base=ov.get("base", ""),
        default_base=card.get("default_base", "") if card else "",
        protocol=ov.get("protocol", ""),
        adapter=ov.get("adapter", ""),
        available=bool(card.get("available")) if card else None,
        models=[ModelCard(**m, provider=label) for m in card.get("models", [])] if card else [],
    )


def _custom_out(p: dict[str, Any], card: dict[str, Any] | None) -> CustomOut:
    cards = {m["alias"]: m for m in (card or {}).get("models", [])}
    models = []
    for m in p["models"]:
        alias = custom_alias(p["id"], m["model"])
        c = cards.get(alias)
        models.append(
            CustomModelOut(
                **m,
                alias=alias,
                available=c["available"] if c else None,
                unavailable_reason=c.get("unavailable_reason") if c else None,
            )
        )
    return CustomOut(
        id=p["id"],
        name=p["name"],
        protocol=p["protocol"],
        adapter=p.get("adapter", ""),
        api_base=p.get("api_base", ""),
        tail=p.get("tail"),
        has_key=bool(p.get("token")),
        broken=bool(p.get("token")) and _decrypt(p["token"]) is None,
        saved_by=p.get("by"),
        saved_at=datetime.fromisoformat(p["at"]) if p.get("at") else None,
        available=bool(card.get("available")) if card else None,
        models=models,
    )


def _reindex_state(cfg: dict[str, Any]) -> ReindexOut:
    if _JOB:
        return ReindexOut(status="running", **_JOB)
    return ReindexOut(**cfg["reindex"]) if cfg.get("reindex") else ReindexOut()


def _status(db: Session, cfg: dict[str, Any], state: dict[str, Any] | None) -> ModelConfigOut:
    cards = {c["var"]: c for c in (state or {}).get("builtin", [])}
    names = list(cards) if state is not None else list(LABELS)
    names += [v for v in cfg.get("keys", {}) if v not in names]
    builtin = [_builtin_out(v, cfg, cards.get(v)) for v in names]
    custom_cards = {c["id"]: c for c in (state or {}).get("custom", [])}
    custom = [_custom_out(p, custom_cards.get(p["id"])) for p in cfg.get("custom", [])]
    models = [m for b in builtin for m in b.models]
    for c in (state or {}).get("custom", []):
        name = next((p.name for p in custom if p.id == c["id"]), c["id"])
        models += [ModelCard(**m, provider=name) for m in c["models"]]
    if state is not None:
        groups, defaults = state.get("groups", {}), state.get("group_defaults", {})
    else:
        groups, defaults = {g: cfg.get("groups", {}).get(g, []) for g in GROUPS}, {}
    settings = get_settings()
    return ModelConfigOut(
        gateway_ok=state is not None,
        builtin=builtin,
        custom=custom,
        groups={g: list(groups.get(g, [])) for g in GROUPS},
        group_defaults={g: list(defaults.get(g, [])) for g in GROUPS},
        models=models,
        embedding_dims=settings.embedding_dims,
        kb_chunks=db.scalar(select(func.count()).select_from(KbChunk)) or 0,
        reindex=_reindex_state(cfg),
        allow_private_base=_allow_private(),
    )


# ---------- 校验 ----------


def _require_admin(user: CurrentUser) -> None:
    ensure_configurer(user, "模型接入由系统管理员配置")


def _invalid(message: str) -> BizError:
    return BizError(ErrorCode.VALIDATION, message)


def _allow_private() -> bool:
    settings = get_settings()
    flag = settings.model_allow_private_base
    return settings.demo_login if flag is None else flag


def check_base(url: str) -> str:
    """接口地址：必须是 http(s)；正式模式下默认不允许解析到内网 / 本机 / 云厂商元数据地址。"""
    url = url.strip()
    if not url:
        return url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise _invalid("接口地址要以 http:// 或 https:// 开头")
    if _allow_private():
        return url
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except (OSError, ValueError) as exc:
        raise _invalid(f"接口地址的域名解析不了：{parts.hostname}") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise _invalid(
                "接口地址指向内网或本机，正式环境默认禁止。"
                "自建模型请在服务器 .env 设置 MODEL_ALLOW_PRIVATE_BASE=true"
            )
    return url


def _check_key(key: str) -> str:
    key = key.strip()
    if key and (len(key) < 4 or re.search(r"\s", key)):
        raise _invalid("Key 格式不对：至少 4 位，不能有空格或换行")
    return key


def _check_protocol(protocol: str, adapter: str) -> str:
    adapter = adapter.strip()
    if protocol == "native" and not ADAPTER_RE.match(adapter):
        raise _invalid("原生协议要填写 LiteLLM 的适配名，例如 deepseek、dashscope、ollama")
    return adapter if protocol == "native" else ""


def _builtin_vars(cfg: dict[str, Any], state: dict[str, Any] | None) -> set[str]:
    if state is not None:
        return {c["var"] for c in state.get("builtin", [])}
    return set(LABELS) | set(cfg.get("keys", {}))


def _embed_alias(cfg: dict[str, Any], state: dict[str, Any] | None) -> str | None:
    groups = (state or {}).get("groups") or cfg.get("groups", {})
    members = groups.get("embed") or []
    return members[0] if members else None


# ---------- 接口 ----------


def get_status(db: Session, user: CurrentUser) -> ModelConfigOut:
    _require_admin(user)
    cfg = _load(db)
    return _status(db, cfg, _gateway_state(cfg))


def save_builtin(db: Session, user: CurrentUser, body: BuiltinIn) -> ModelConfigOut:
    """保存内置厂商的 Key / 地址 / 协议，并推送给网关。网关暂时连不上也先存下，恢复后自动推送。"""
    _require_admin(user)
    var = body.var.strip()
    if not VAR_RE.match(var):
        raise _invalid("厂商变量名不正确")
    cfg = _load(db, lock=True)
    if var not in _builtin_vars(cfg, _gateway_state(cfg)):
        raise _invalid(f"网关的模型清单里没有用到 {var}")
    base, adapter = check_base(body.base), _check_protocol(body.protocol, body.adapter)
    if body.key is not None:
        key = _check_key(body.key)
        keys = cfg.setdefault("keys", {})
        if key:
            keys[var] = _seal(key, user)
        else:
            keys.pop(var, None)
    overrides = cfg.setdefault("builtin", {})
    if base or body.protocol:
        overrides[var] = {"base": base, "protocol": body.protocol, "adapter": adapter}
    else:
        overrides.pop(var, None)
    _store(db, user, cfg)
    return _status(db, cfg, _push_quietly(cfg))


def test_builtin(db: Session, user: CurrentUser, body: BuiltinTestIn) -> TestOut:
    """用表单上的值发一次最小请求，不保存。"""
    _require_admin(user)
    base, adapter = check_base(body.base), _check_protocol(body.protocol, body.adapter)
    key = _check_key(body.key or "") or None
    if key is None:  # 没填：网页上存过就用它，否则由网关用 .env 的
        key = _decrypt(_load(db).get("keys", {}).get(body.var, {}).get("token"))
    override = {"key": key or "", "base": base, "protocol": body.protocol, "adapter": adapter}
    return _test({"var": body.var, "override": override})


def _test(payload: dict[str, Any]) -> TestOut:
    try:
        result = client.gateway_admin("POST", "test", payload)
    except BizError as exc:
        return TestOut(ok=False, error=f"连不上模型网关：{exc.message}")
    return TestOut.model_validate(result)


def _custom_models(provider_id: str, models: list[CustomModelIn]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for m in models:
        name = m.model.strip()
        alias = custom_alias(provider_id, name)
        if alias == f"{provider_id}-" or alias in seen:
            raise _invalid(f"模型名重复或无效：{name}")
        seen.add(alias)
        caps = m.capabilities.model_dump()
        if m.kind != "embedding":
            caps["dims"] = None
        out.append({"model": name, "kind": m.kind, "capabilities": caps})
    return out


def save_custom(db: Session, user: CurrentUser, provider_id: str, body: CustomIn) -> ModelConfigOut:
    """新建或修改一个自定义厂商（按 id）。"""
    _require_admin(user)
    if not ID_RE.match(provider_id):
        raise _invalid("厂商标识只能用小写字母、数字和短横线，2～24 位，字母开头")
    cfg = _load(db, lock=True)
    state = _gateway_state(cfg)
    adapter = _check_protocol(body.protocol, body.adapter)
    api_base = check_base(body.api_base)
    if body.protocol == "openai_compat" and not api_base:
        raise _invalid("OpenAI 兼容协议要填写接口地址")
    models = _custom_models(provider_id, body.models)
    aliases = {custom_alias(provider_id, m["model"]) for m in models}
    builtin_aliases = {m["alias"] for c in (state or {}).get("builtin", []) for m in c["models"]}
    builtin_aliases |= {"chat-default", *GROUPS}  # 分组名也不能和模型别名重复
    if aliases & builtin_aliases:
        raise _invalid(
            f"模型别名和内置模型重复：{sorted(aliases & builtin_aliases)}，换一个厂商标识"
        )
    providers = cfg.setdefault("custom", [])
    old = next((p for p in providers if p["id"] == provider_id), None)
    embed = _embed_alias(cfg, state)
    if old and embed and embed.startswith(f"{provider_id}-") and embed not in aliases:
        raise _invalid("知识库正在用这个厂商的向量模型，先在「默认模型」里换掉再删除这个模型")
    entry: dict[str, Any] = {
        "id": provider_id,
        "name": body.name.strip(),
        "protocol": body.protocol,
        "adapter": adapter,
        "api_base": api_base,
        "models": models,
    }
    if body.key is None and old:
        entry.update({k: old[k] for k in ("token", "tail", "by", "at") if k in old})
    elif body.key:
        entry.update(_seal(_check_key(body.key), user))
    entry.setdefault("by", user.name)
    entry.setdefault("at", datetime.now(UTC).isoformat())
    cfg["custom"] = [p for p in providers if p["id"] != provider_id] + [entry]
    _store(db, user, cfg)
    return _status(db, cfg, _push_quietly(cfg))


def delete_custom(db: Session, user: CurrentUser, provider_id: str) -> ModelConfigOut:
    _require_admin(user)
    cfg = _load(db, lock=True)
    providers = cfg.get("custom", [])
    if not any(p["id"] == provider_id for p in providers):
        raise BizError(ErrorCode.NOT_FOUND, "没有这个自定义厂商")
    embed = _embed_alias(cfg, _gateway_state(cfg))
    if embed and embed.startswith(f"{provider_id}-"):
        raise _invalid("知识库正在用这个厂商的向量模型，先在「默认模型」里换掉再删除")
    cfg["custom"] = [p for p in providers if p["id"] != provider_id]
    groups = cfg.get("groups", {})
    for g, members in groups.items():
        groups[g] = [a for a in members if not a.startswith(f"{provider_id}-")]
    _store(db, user, cfg)
    return _status(db, cfg, _push_quietly(cfg))


def test_custom(db: Session, user: CurrentUser, provider_id: str, body: CustomTestIn) -> TestOut:
    """测一个自定义模型（不保存）：连得通就顺便检测能力，Embedding 返回向量维度。"""
    _require_admin(user)
    if not ID_RE.match(provider_id):
        raise _invalid("厂商标识只能用小写字母、数字和短横线，2～24 位，字母开头")
    adapter = _check_protocol(body.protocol, body.adapter)
    api_base = check_base(body.api_base)
    key = _check_key(body.key or "") or None
    if key is None:
        old = next((p for p in _load(db).get("custom", []) if p["id"] == provider_id), {})
        key = _decrypt(old.get("token"))
    provider = {
        "id": provider_id,
        "protocol": body.protocol,
        "adapter": adapter,
        "api_base": api_base,
        "api_key": key or "",
        "models": _custom_models(provider_id, [body.model]),
    }
    return _test({"provider": provider, "detect": body.detect})


def save_groups(db: Session, user: CurrentUser, body: GroupsIn) -> ModelConfigOut:
    """对话、重排的主用和备用顺序（第一个是主用，出错时按顺序切到下一个）。"""
    _require_admin(user)
    cfg = _load(db, lock=True)
    state = _gateway_state(cfg)
    if state is None:
        raise BizError(ErrorCode.UPSTREAM, "模型网关连不上，暂时不能调整默认模型")
    cards = {m.alias: m for m in _status(db, cfg, state).models}

    def pick(aliases: list[str], kind: Kind, label: str) -> list[str]:
        out: list[str] = []
        for a in aliases:
            card = cards.get(a)
            if card is None or card.kind != kind or (kind == "chat" and not card.tools):
                raise _invalid(f"{a} 不能用作{label}")
            if a not in out:
                out.append(a)
        return out

    groups = cfg.setdefault("groups", {})
    groups["chat-agent"] = pick(body.chat, "chat", "对话模型（需要支持工具调用）")
    groups["rerank"] = pick(body.rerank, "rerank", "重排模型")
    _store(db, user, cfg)
    return _status(db, cfg, _push_quietly(cfg))


# ---------- 切换知识库向量模型 ----------


def _load_chunks(db: Session) -> list[tuple[Any, str]]:
    rows = db.execute(select(KbChunk.id, KbChunk.doc_name, KbChunk.section, KbChunk.content)).all()
    return [(r.id, embedding_text(Chunk("", None, r.doc_name, r.section, r.content))) for r in rows]


def _write_vectors(db: Session, vectors: dict[Any, list[float]]) -> None:
    db.execute(update(KbChunk), [{"id": k, "embedding": v} for k, v in vectors.items()])


def _embed_all(alias: str, chunks: list[tuple[Any, str]], vectors: dict[Any, list[float]]) -> None:
    dims = get_settings().embedding_dims
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        out = client.embed_texts([text for _, text in batch], model=alias)
        if out and len(out[0]) != dims:
            raise _invalid(f"这个模型输出 {len(out[0])} 维向量，知识库需要 {dims} 维")
        vectors.update((cid, v) for (cid, _), v in zip(batch, out, strict=True))
        _JOB["done"] = len(vectors)


def _reindex(alias: str, by: str) -> None:
    """用新模型把全部知识块重新向量化；全部算完再一次性写入并切换分组，中途失败不影响现有检索。"""
    status: dict[str, Any] = {"target": alias, "by": by}
    vectors: dict[Any, list[float]] = {}
    try:
        with session_scope() as db:
            chunks = _load_chunks(db)
        _JOB["total"] = len(chunks)
        _embed_all(alias, chunks, vectors)
        with session_scope() as db:
            cfg = _load(db, lock=True)
            # 重建期间新上传的文档：用新模型补上
            fresh = [c for c in _load_chunks(db) if c[0] not in vectors]
            _JOB["total"] += len(fresh)
            _embed_all(alias, fresh, vectors)
            _write_vectors(db, vectors)
            cfg.setdefault("groups", {})["embed"] = [alias]
            cfg["reindex"] = {
                **status,
                "status": "done",
                "total": len(vectors),
                "done": len(vectors),
            }
            cfg["reindex"]["at"] = datetime.now(UTC).isoformat()
            _store(db, None, cfg)
        _push_quietly(cfg)
        logger.info("knowledge reindexed with %s: %d chunks", alias, len(vectors))
    except Exception as exc:
        logger.exception("knowledge reindex with %s failed", alias)
        message = exc.message if isinstance(exc, BizError) else type(exc).__name__
        with session_scope() as db:
            cfg = _load(db, lock=True)
            cfg["reindex"] = {
                **status,
                "status": "failed",
                "error": message[:300],
                "done": len(vectors),
                "total": _JOB.get("total", 0),
                "at": datetime.now(UTC).isoformat(),
            }
            _store(db, None, cfg)
    finally:
        _JOB.clear()


def switch_embedding(db: Session, user: CurrentUser, body: EmbeddingIn) -> ModelConfigOut:
    """切换知识库向量模型：后台重建全部向量，完成后自动切换。"""
    _require_admin(user)
    cfg = _load(db)
    state = _gateway_state(cfg)
    if state is None:
        raise BizError(ErrorCode.UPSTREAM, "模型网关连不上，暂时不能切换向量模型")
    status = _status(db, cfg, state)
    card = next((m for m in status.models if m.alias == body.alias), None)
    if card is None or card.kind != "embedding":
        raise _invalid(f"{body.alias} 不是向量（Embedding）模型")
    if not card.available:
        raise _invalid(f"{body.alias} 现在不可用，先配好 Key 并测试连接")
    if card.dims and card.dims != status.embedding_dims:
        raise _invalid(f"这个模型输出 {card.dims} 维向量，知识库需要 {status.embedding_dims} 维")
    if status.groups["embed"][:1] == [body.alias]:
        raise _invalid("知识库已经在用这个模型")
    with _JOB_LOCK:
        if _JOB:
            raise _invalid("正在重建知识库向量，完成后再切换")
        _JOB.update(target=body.alias, done=0, total=status.kb_chunks, by=user.name)
        _JOB["at"] = datetime.now(UTC)
    threading.Thread(
        target=_reindex, args=(body.alias, user.name), name="kb-reindex", daemon=True
    ).start()
    return _status(db, cfg, state)


# ---------- 后台同步 ----------


def sync_once() -> None:
    with session_scope() as db:
        cfg = _load(db)
    _gateway_state(cfg)


def start_sync() -> threading.Event:
    """后台每分钟比对一次：网关单独重启后丢了网页上的配置，由这里补推。返回停止信号。"""
    stop = threading.Event()

    def loop() -> None:
        while True:
            try:
                sync_once()
            except Exception:
                logger.exception("model config sync failed")
            if stop.wait(SYNC_SECONDS):
                return

    threading.Thread(target=loop, name="model-config-sync", daemon=True).start()
    return stop
