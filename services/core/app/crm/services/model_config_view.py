"""模型接入页面的状态：把存库的配置和网关的模型清单拼成 ModelConfigOut（不含完整 Key）。"""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.crm.models import KbChunk
from app.crm.schemas.model_config import (
    BuiltinOut,
    CustomModelOut,
    CustomOut,
    ModelCard,
    ModelConfigOut,
    ReindexOut,
)
from app.crm.services import model_config_reindex as reindex
from app.crm.services.model_config_store import GROUPS, LABELS, allow_private, custom_alias, decrypt


def _key_source(
    entry: dict[str, Any] | None, broken: bool, card: dict[str, Any] | None
) -> Literal["web", "env", "none"]:
    if entry is not None and not broken:
        return "web"
    if card and card.get("env_configured"):
        return "env"
    return "none"


def _builtin_out(var: str, cfg: dict[str, Any], card: dict[str, Any] | None) -> BuiltinOut:
    label, hint = LABELS.get(var, (var, "按厂商文档申请"))
    entry = cfg.get("keys", {}).get(var)
    broken = entry is not None and decrypt(entry["token"]) is None
    ov = cfg.get("builtin", {}).get(var, {})
    return BuiltinOut(
        var=var,
        label=label,
        hint=hint,
        key_source=_key_source(entry, broken, card),
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
        broken=bool(p.get("token")) and decrypt(p["token"]) is None,
        saved_by=p.get("by"),
        saved_at=datetime.fromisoformat(p["at"]) if p.get("at") else None,
        available=bool(card.get("available")) if card else None,
        models=models,
    )


def _reindex_state(cfg: dict[str, Any]) -> ReindexOut:
    if reindex.JOB:
        return ReindexOut(status="running", **reindex.JOB)
    return ReindexOut(**cfg["reindex"]) if cfg.get("reindex") else ReindexOut()


def _groups(cfg: dict[str, Any], state: dict[str, Any] | None) -> tuple[dict, dict]:
    if state is not None:
        return state.get("groups", {}), state.get("group_defaults", {})
    return {g: cfg.get("groups", {}).get(g, []) for g in GROUPS}, {}


def status(db: Session, cfg: dict[str, Any], state: dict[str, Any] | None) -> ModelConfigOut:
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
    groups, defaults = _groups(cfg, state)
    return ModelConfigOut(
        gateway_ok=state is not None,
        builtin=builtin,
        custom=custom,
        groups={g: list(groups.get(g, [])) for g in GROUPS},
        group_defaults={g: list(defaults.get(g, [])) for g in GROUPS},
        models=models,
        embedding_dims=get_settings().embedding_dims,
        kb_chunks=db.scalar(select(func.count()).select_from(KbChunk)) or 0,
        reindex=_reindex_state(cfg),
        allow_private_base=allow_private(),
    )
