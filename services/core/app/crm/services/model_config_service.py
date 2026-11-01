"""模型接入：管理员在网页上配置厂商与默认模型，加密存库，推给网关立即生效。

- 内置厂商（models.yaml 里的混元、DeepSeek、通义）：可以改 Key、接口地址、协议；
  网页上填的优先，没填的用 .env；
- 自定义厂商：任意 OpenAI 兼容接口或 LiteLLM 原生适配（Kimi、智谱、自建 vLLM / Ollama 等）；
- 默认模型：对话（chat-agent）、重排（rerank）的主用和备用顺序；知识库向量（embed）单独切换；
- 网页上只显示末 4 位，任何接口都不返回完整 Key；操作日志不记请求体；
- 接口地址在正式模式下默认不允许指向内网或本机（防止借服务器访问内网），自建模型需在 .env 打开
  MODEL_ALLOW_PRIVATE_BASE；
- 网关只把配置放在内存里：core 启动时和之后每分钟比对一次版本，网关重启过就重新推送。

拆分：加密 / 存储 / 推送 / 校验在 model_config_store，页面状态在 model_config_view，
向量重建在 model_config_reindex；这里只放对外的接口。
"""

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.db import session_scope
from app.common.errors import BizError, ErrorCode
from app.crm.schemas.model_config import (
    BuiltinIn,
    BuiltinTestIn,
    CustomIn,
    CustomModelIn,
    CustomTestIn,
    EmbeddingIn,
    GroupsIn,
    Kind,
    ModelConfigOut,
    TestOut,
)
from app.crm.services import model_config_reindex as reindex
from app.crm.services import model_config_store as store
from app.crm.services.model_config_store import (
    GROUPS,
    ID_RE,
    LABELS,
    VAR_RE,
    check_base,
    check_key,
    check_protocol,
    custom_alias,
    invalid,
    require_admin,
)
from app.crm.services.model_config_view import status
from app.llm import client

logger = logging.getLogger(__name__)

SYNC_SECONDS = 60
_BAD_ID = "厂商标识只能用小写字母、数字和短横线，2～24 位，字母开头"


def _builtin_vars(cfg: dict[str, Any], state: dict[str, Any] | None) -> set[str]:
    if state is not None:
        return {c["var"] for c in state.get("builtin", [])}
    return set(LABELS) | set(cfg.get("keys", {}))


def _embed_alias(cfg: dict[str, Any], state: dict[str, Any] | None) -> str | None:
    groups = (state or {}).get("groups") or cfg.get("groups", {})
    members = groups.get("embed") or []
    return members[0] if members else None


def _save(db: Session, user: CurrentUser, cfg: dict[str, Any]) -> ModelConfigOut:
    store.store(db, user, cfg)
    return status(db, cfg, store.push_quietly(cfg))


# ---------- 内置厂商 ----------


def get_status(db: Session, user: CurrentUser) -> ModelConfigOut:
    require_admin(user)
    cfg = store.load(db)
    return status(db, cfg, store.gateway_state(cfg))


def save_builtin(db: Session, user: CurrentUser, body: BuiltinIn) -> ModelConfigOut:
    """保存内置厂商的 Key / 地址 / 协议，并推送给网关。网关暂时连不上也先存下，恢复后自动推送。"""
    require_admin(user)
    var = body.var.strip()
    if not VAR_RE.match(var):
        raise invalid("厂商变量名不正确")
    cfg = store.load(db, lock=True)
    if var not in _builtin_vars(cfg, store.gateway_state(cfg)):
        raise invalid(f"网关的模型清单里没有用到 {var}")
    base, adapter = check_base(body.base), check_protocol(body.protocol, body.adapter)
    if body.key is not None:
        key = check_key(body.key)
        keys = cfg.setdefault("keys", {})
        if key:
            keys[var] = store.seal(key, user)
        else:
            keys.pop(var, None)
    overrides = cfg.setdefault("builtin", {})
    if base or body.protocol:
        overrides[var] = {"base": base, "protocol": body.protocol, "adapter": adapter}
    else:
        overrides.pop(var, None)
    return _save(db, user, cfg)


def test_builtin(db: Session, user: CurrentUser, body: BuiltinTestIn) -> TestOut:
    """用表单上的值发一次最小请求，不保存。"""
    require_admin(user)
    base, adapter = check_base(body.base), check_protocol(body.protocol, body.adapter)
    key = check_key(body.key or "") or None
    if key is None:  # 没填：网页上存过就用它，否则由网关用 .env 的
        key = store.decrypt(store.load(db).get("keys", {}).get(body.var, {}).get("token"))
    override = {"key": key or "", "base": base, "protocol": body.protocol, "adapter": adapter}
    return _test({"var": body.var, "override": override})


def _test(payload: dict[str, Any]) -> TestOut:
    try:
        result = client.gateway_admin("POST", "test", payload)
    except BizError as exc:
        return TestOut(ok=False, error=f"连不上模型网关：{exc.message}")
    return TestOut.model_validate(result)


# ---------- 自定义厂商 ----------


def _custom_models(provider_id: str, models: list[CustomModelIn]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for m in models:
        name = m.model.strip()
        alias = custom_alias(provider_id, name)
        if alias == f"{provider_id}-" or alias in seen:
            raise invalid(f"模型名重复或无效：{name}")
        seen.add(alias)
        caps = m.capabilities.model_dump()
        if m.kind != "embedding":
            caps["dims"] = None
        out.append({"model": name, "kind": m.kind, "capabilities": caps})
    return out


def _check_aliases(state: dict[str, Any] | None, aliases: set[str]) -> None:
    builtin_aliases = {m["alias"] for c in (state or {}).get("builtin", []) for m in c["models"]}
    builtin_aliases |= {"chat-default", *GROUPS}  # 分组名也不能和模型别名重复
    if aliases & builtin_aliases:
        raise invalid(
            f"模型别名和内置模型重复：{sorted(aliases & builtin_aliases)}，换一个厂商标识"
        )


def _custom_entry(provider_id: str, body: CustomIn) -> dict[str, Any]:
    adapter = check_protocol(body.protocol, body.adapter)
    api_base = check_base(body.api_base)
    if body.protocol == "openai_compat" and not api_base:
        raise invalid("OpenAI 兼容协议要填写接口地址")
    return {
        "id": provider_id,
        "name": body.name.strip(),
        "protocol": body.protocol,
        "adapter": adapter,
        "api_base": api_base,
        "models": _custom_models(provider_id, body.models),
    }


def save_custom(db: Session, user: CurrentUser, provider_id: str, body: CustomIn) -> ModelConfigOut:
    """新建或修改一个自定义厂商（按 id）。"""
    require_admin(user)
    if not ID_RE.match(provider_id):
        raise invalid(_BAD_ID)
    cfg = store.load(db, lock=True)
    state = store.gateway_state(cfg)
    entry = _custom_entry(provider_id, body)
    aliases = {custom_alias(provider_id, m["model"]) for m in entry["models"]}
    _check_aliases(state, aliases)
    providers = cfg.setdefault("custom", [])
    old = next((p for p in providers if p["id"] == provider_id), None)
    embed = _embed_alias(cfg, state)
    if old and embed and embed.startswith(f"{provider_id}-") and embed not in aliases:
        raise invalid("知识库正在用这个厂商的向量模型，先在「默认模型」里换掉再删除这个模型")
    if body.key is None and old:
        entry.update({k: old[k] for k in ("token", "tail", "by", "at") if k in old})
    elif body.key:
        entry.update(store.seal(check_key(body.key), user))
    entry.setdefault("by", user.name)
    entry.setdefault("at", datetime.now(UTC).isoformat())
    cfg["custom"] = [p for p in providers if p["id"] != provider_id] + [entry]
    return _save(db, user, cfg)


def delete_custom(db: Session, user: CurrentUser, provider_id: str) -> ModelConfigOut:
    require_admin(user)
    cfg = store.load(db, lock=True)
    providers = cfg.get("custom", [])
    if not any(p["id"] == provider_id for p in providers):
        raise BizError(ErrorCode.NOT_FOUND, "没有这个自定义厂商")
    embed = _embed_alias(cfg, store.gateway_state(cfg))
    if embed and embed.startswith(f"{provider_id}-"):
        raise invalid("知识库正在用这个厂商的向量模型，先在「默认模型」里换掉再删除")
    cfg["custom"] = [p for p in providers if p["id"] != provider_id]
    groups = cfg.get("groups", {})
    for g, members in groups.items():
        groups[g] = [a for a in members if not a.startswith(f"{provider_id}-")]
    return _save(db, user, cfg)


def test_custom(db: Session, user: CurrentUser, provider_id: str, body: CustomTestIn) -> TestOut:
    """测一个自定义模型（不保存）：连得通就顺便检测能力，Embedding 返回向量维度。"""
    require_admin(user)
    if not ID_RE.match(provider_id):
        raise invalid(_BAD_ID)
    adapter = check_protocol(body.protocol, body.adapter)
    api_base = check_base(body.api_base)
    key = check_key(body.key or "") or None
    if key is None:
        old = next((p for p in store.load(db).get("custom", []) if p["id"] == provider_id), {})
        key = store.decrypt(old.get("token"))
    provider = {
        "id": provider_id,
        "protocol": body.protocol,
        "adapter": adapter,
        "api_base": api_base,
        "api_key": key or "",
        "models": _custom_models(provider_id, [body.model]),
    }
    return _test({"provider": provider, "detect": body.detect})


# ---------- 默认模型 ----------


def save_groups(db: Session, user: CurrentUser, body: GroupsIn) -> ModelConfigOut:
    """对话、重排的主用和备用顺序（第一个是主用，出错时按顺序切到下一个）。"""
    require_admin(user)
    cfg = store.load(db, lock=True)
    state = store.gateway_state(cfg)
    if state is None:
        raise BizError(ErrorCode.UPSTREAM, "模型网关连不上，暂时不能调整默认模型")
    cards = {m.alias: m for m in status(db, cfg, state).models}

    def pick(aliases: list[str], kind: Kind, label: str) -> list[str]:
        out: list[str] = []
        for a in aliases:
            card = cards.get(a)
            if card is None or card.kind != kind or (kind == "chat" and not card.tools):
                raise invalid(f"{a} 不能用作{label}")
            if a not in out:
                out.append(a)
        return out

    groups = cfg.setdefault("groups", {})
    groups["chat-agent"] = pick(body.chat, "chat", "对话模型（需要支持工具调用）")
    groups["rerank"] = pick(body.rerank, "rerank", "重排模型")
    return _save(db, user, cfg)


def switch_embedding(db: Session, user: CurrentUser, body: EmbeddingIn) -> ModelConfigOut:
    """切换知识库向量模型：后台重建全部向量，完成后自动切换。"""
    require_admin(user)
    cfg = store.load(db)
    state = store.gateway_state(cfg)
    if state is None:
        raise BizError(ErrorCode.UPSTREAM, "模型网关连不上，暂时不能切换向量模型")
    current = status(db, cfg, state)
    card = next((m for m in current.models if m.alias == body.alias), None)
    if card is None or card.kind != "embedding":
        raise invalid(f"{body.alias} 不是向量（Embedding）模型")
    if not card.available:
        raise invalid(f"{body.alias} 现在不可用，先配好 Key 并测试连接")
    if card.dims and card.dims != current.embedding_dims:
        raise invalid(f"这个模型输出 {card.dims} 维向量，知识库需要 {current.embedding_dims} 维")
    if current.groups["embed"][:1] == [body.alias]:
        raise invalid("知识库已经在用这个模型")
    reindex.start(body.alias, user.name, current.kb_chunks)
    return status(db, cfg, state)


# ---------- 后台同步 ----------


def sync_once() -> None:
    with session_scope() as db:
        cfg = store.load(db)
    store.gateway_state(cfg)


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
