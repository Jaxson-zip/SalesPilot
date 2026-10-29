"""网页上维护的配置（仅管理员）：通用业务规则、行业包参数、产品价格、行业包知识库文档。

文件（rules.yaml / catalog.json / knowledge/）是默认值，网页上的改动存在 config_overrides 表，
保存后立即生效；每一项都可以「恢复默认」（删除这条改动）。
"""

import math
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.crm.models import ConfigOverride, KbChunk, User
from app.llm.client import embed_texts
from app.packs.base import Catalog, CatalogItem
from app.packs.registry import PackInfo, get_pack
from app.rag.chunking import dedupe, embedding_text
from app.rag.ingest import EMBED_BATCH, uploaded_knowledge_dir
from app.rag.loaders import LOADERS, load_file
from app.rules import overrides
from app.rules.loader import RULES_FILE, RuleSet, deep_merge, load_raw_rules, read_yaml

Kind = Literal[
    "percent", "money", "int", "float", "cities", "percent_list", "stages", "megabytes", "bool"
]


class SettingField(BaseModel):
    """一个可在网页上修改的配置项。值按存储单位：比例是小数、金额是分、大小是字节。"""

    key: str  # 点分路径
    label: str
    group: str
    kind: Kind
    unit: str = ""
    min: float | None = None
    max: float | None = None
    help: str = ""


class SettingValue(SettingField):
    value: Any
    default: Any
    overridden: bool
    updated_at: datetime | None = None
    updated_by: str | None = None


class SettingsOut(BaseModel):
    groups: list[str]
    fields: list[SettingValue]


class SettingsUpdate(BaseModel):
    """key → 新值；null 表示恢复默认。"""

    values: dict[str, Any]


def _f(key: str, label: str, group: str, kind: Kind, **kw: Any) -> SettingField:
    return SettingField(key=key, label=label, group=group, kind=kind, **kw)


_STAGE_LABELS = {
    "lead": "线索",
    "qualified": "需求确认",
    "proposal": "方案报价",
    "negotiation": "商务谈判",
}

GLOBAL_FIELDS: list[SettingField] = [
    _f(
        "margin.floor_rate",
        "毛利底线",
        "报价与审批",
        "percent",
        min=0,
        max=0.9,
        help="报价毛利低于该值，需要主管审批",
    ),
    _f(
        "discount.max_rate",
        "销售折扣权限",
        "报价与审批",
        "percent",
        min=0,
        max=0.9,
        help="销售可以直接给的最大折扣，超过需要主管审批",
    ),
    _f("quote.valid_days", "报价有效期", "报价与审批", "int", unit="天", min=1, max=365),
    _f(
        "quote.followup_days",
        "发送报价后跟进",
        "报价与审批",
        "int",
        unit="天",
        min=0,
        max=60,
        help="报价单标记已发送时自动建一条跟进任务，这么多天后到期；0 表示不建",
    ),
    _f("commission.rates.hardware", "提成比例 · 硬件", "提成", "percent", min=0, max=0.5),
    _f("commission.rates.software", "提成比例 · 软件", "提成", "percent", min=0, max=0.5),
    _f("commission.rates.service", "提成比例 · 服务", "提成", "percent", min=0, max=0.5),
    _f(
        "commission.low_margin_floor",
        "低毛利线",
        "提成",
        "percent",
        min=0,
        max=0.9,
        help="合同毛利低于该值时，提成按下方系数打折",
    ),
    _f("commission.low_margin_factor", "低毛利提成系数", "提成", "float", unit="倍", min=0, max=1),
    _f("expense.entertainment_per_person", "客户招待标准", "报销", "money", unit="元/人", min=0),
    _f("expense.hotel.per_night", "住宿标准 · 其他城市", "报销", "money", unit="元/晚", min=0),
    _f(
        "expense.hotel.per_night_tier1", "住宿标准 · 一线城市", "报销", "money", unit="元/晚", min=0
    ),
    _f(
        "expense.hotel.tier1_cities",
        "一线城市",
        "报销",
        "cities",
        help="城市名包含其中任意一个即按一线标准",
    ),
    *[
        _f(
            f"pipeline.stage_win_rate.{k}",
            f"默认赢率 · {v}",
            "商机",
            "int",
            unit="%",
            min=0,
            max=100,
        )
        for k, v in _STAGE_LABELS.items()
    ],
    _f(
        "pipeline.stale_days",
        "停滞提醒",
        "商机",
        "int",
        unit="天",
        min=1,
        max=365,
        help="进行中的商机超过这么多天没有动态，提醒负责人",
    ),
    _f(
        "payment.schedule",
        "标准回款计划",
        "回款",
        "stages",
        help="合同生成时按此拆分回款期次，比例合计必须是 100%",
    ),
    _f(
        "payment.remind_days",
        "到期前提醒",
        "回款",
        "int",
        unit="天",
        min=0,
        max=30,
        help="每期回款到期前这么多天提醒合同负责人，可以提前开票、提醒客户付款；0 表示不提醒",
    ),
    _f(
        "payment.followup_days",
        "逾期跟进",
        "回款",
        "int",
        unit="天",
        min=1,
        max=365,
        help="逾期超过这么多天，每周跟进",
    ),
    _f(
        "payment.block_days",
        "逾期暂停新报价",
        "回款",
        "int",
        unit="天",
        min=1,
        max=730,
        help="逾期超过这么多天，暂停该客户新报价的审批",
    ),
    _f("attachment.max_bytes", "单个票据大小上限", "票据", "megabytes", unit="MB", min=1, max=50),
    _f(
        "privacy.phone_reveal_daily_limit",
        "每天查看完整电话次数",
        "数据安全",
        "int",
        unit="次",
        min=0,
        max=1000,
        help="联系人电话默认脱敏显示，点「查看」才显示完整号码并记入操作日志",
    ),
    _f(
        "privacy.export_max_rows",
        "单次导出上限",
        "数据安全",
        "int",
        unit="条",
        min=1,
        max=10000,
        help="列表导出 CSV 的最大条数；销售不能导出客户和商机名单",
    ),
    _f(
        "agent.margin_max_retries",
        "毛利不达标时重新配置次数",
        "AI 助手",
        "int",
        unit="次",
        min=0,
        max=5,
    ),
    _f("agent.max_tool_calls", "单轮最多调用工具次数", "AI 助手", "int", unit="次", min=1, max=20),
    _f(
        "ai_usage.input_price_per_million",
        "输入单价",
        "AI 用量",
        "float",
        unit="元/百万 tokens",
        min=0,
        max=1000,
        help="按所用模型的官方价格填写，用于估算 AI 费用",
    ),
    _f(
        "ai_usage.output_price_per_million",
        "输出单价",
        "AI 用量",
        "float",
        unit="元/百万 tokens",
        min=0,
        max=1000,
    ),
    _f(
        "ai_usage.monthly_budget",
        "全公司月度预算",
        "AI 用量",
        "money",
        min=0,
        help="超过 80% 时 AI 用量页提醒；0 表示不设，不会拦截调用",
    ),
    _f("ai_usage.team_monthly_budget", "每个团队月度预算", "AI 用量", "money", min=0),
    _f(
        "ai_usage.user_daily_tokens",
        "每人每日 tokens 上限",
        "AI 用量",
        "int",
        unit="tokens",
        min=0,
        help="超过后当天不能再发起 AI 对话、识别和日报草稿（已在确认中的操作不受影响）；0 表示不限",
    ),
]


def _pack_fields(pack: PackInfo) -> list[SettingField]:
    """行业包可改的参数在 pack.yaml 的 settings 段声明；毛利底线每个行业包都可以单独设置。"""
    manifest = read_yaml(pack.path / "pack.yaml")
    fields = [
        _f(
            "margin.floor_rate",
            "本行业毛利底线",
            "报价",
            "percent",
            min=0,
            max=0.9,
            help="不单独设置时沿用通用规则",
        ),
    ]
    return fields + [SettingField.model_validate(x) for x in manifest.get("settings", [])]


# ---------- 读取 ----------


def _require_admin(user: CurrentUser) -> None:
    if user.role is not Role.ADMIN:
        raise BizError(ErrorCode.FORBIDDEN, "仅管理员可以修改配置")


def _rows(db: Session, scope: str) -> dict[str, tuple[ConfigOverride, str | None]]:
    stmt = (
        select(ConfigOverride, User.name)
        .outerjoin(User, User.id == ConfigOverride.updated_by)
        .where(ConfigOverride.scope == scope)
    )
    return {row.key: (row, name) for row, name in db.execute(stmt).all()}


def _defaults(scope: str) -> dict[str, Any]:
    """没有本范围网页改动时的值。

    通用：rules.yaml；行业包：通用规则（含网页改动）+ 行业包 rules.yaml。
    """
    if scope == overrides.GLOBAL:
        return read_yaml(RULES_FILE)
    return load_raw_rules(get_pack(scope).rules_file)


def _settings(db: Session, scope: str, fields: list[SettingField]) -> SettingsOut:
    defaults = _defaults(scope)
    current = load_raw_rules(
        None if scope == overrides.GLOBAL else get_pack(scope).rules_file,
        None if scope == overrides.GLOBAL else scope,
    )
    rows = _rows(db, scope)
    out = []
    for f in fields:
        row, name = rows.get(f.key, (None, None))
        out.append(
            SettingValue(
                **f.model_dump(),
                value=overrides.get_path(current, f.key),
                default=overrides.get_path(defaults, f.key),
                overridden=row is not None,
                updated_at=row.updated_at if row else None,
                updated_by=name,
            )
        )
    groups = list(dict.fromkeys(f.group for f in fields))
    return SettingsOut(groups=groups, fields=out)


def get_global_settings(db: Session, user: CurrentUser) -> SettingsOut:
    _require_admin(user)
    return _settings(db, overrides.GLOBAL, GLOBAL_FIELDS)


def get_pack_settings(db: Session, user: CurrentUser, pack_id: str) -> SettingsOut:
    _require_admin(user)
    return _settings(db, pack_id, _pack_fields(get_pack(pack_id)))


# ---------- 校验与保存 ----------


def _invalid(key: str, msg: str) -> BizError:
    return BizError(
        ErrorCode.VALIDATION, msg, {"errors": [{"loc": ["body", "values", key], "msg": msg}]}
    )


def _number(f: SettingField, v: Any, *, integer: bool) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise _invalid(f.key, f"「{f.label}」必须是数字")
    if integer and int(v) != v:
        raise _invalid(f.key, f"「{f.label}」必须是整数")
    scale = 1024 * 1024 if f.kind == "megabytes" else 1
    lo = f.min * scale if f.min is not None else None
    hi = f.max * scale if f.max is not None else None
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise _invalid(f.key, f"「{f.label}」超出允许范围")
    return float(v)


def _clean(f: SettingField, v: Any) -> Any:
    """按类型校验并规范化（存储单位：比例小数、金额分、大小字节）。"""
    if f.kind in ("int", "money", "megabytes"):
        return int(_number(f, v, integer=True))
    if f.kind in ("percent", "float"):
        return round(_number(f, v, integer=False), 6)
    if f.kind == "cities":
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise _invalid(f.key, f"「{f.label}」必须是城市列表")
        cities = list(dict.fromkeys(x.strip() for x in v if x.strip()))
        if not cities:
            raise _invalid(f.key, f"「{f.label}」至少要有一个城市")
        return cities
    if f.kind == "percent_list":
        if not isinstance(v, list) or not v:
            raise _invalid(f.key, f"「{f.label}」至少要有一项")
        return [round(_number(f, x, integer=False), 6) for x in v]
    if f.kind == "stages":
        return _clean_stages(f, v)
    if f.kind == "bool":
        if not isinstance(v, bool):
            raise _invalid(f.key, f"「{f.label}」只能是开或关")
        return v
    raise _invalid(f.key, "不支持的配置类型")


def _clean_stages(f: SettingField, v: Any) -> list[dict[str, Any]]:
    if not isinstance(v, list) or not 1 <= len(v) <= 6:
        raise _invalid(f.key, "回款计划需要 1–6 期")
    out = []
    for s in v:
        if not isinstance(s, dict) or not str(s.get("name", "")).strip():
            raise _invalid(f.key, "每一期都要有名称")
        ratio, days = s.get("ratio"), s.get("due_days")
        if not isinstance(ratio, int | float) or not 0 < ratio <= 1:
            raise _invalid(f.key, f"「{s['name']}」的比例要在 0–100% 之间")
        if not isinstance(days, int) or isinstance(days, bool) or not 0 <= days <= 3650:
            raise _invalid(f.key, f"「{s['name']}」的到期天数要在 0–3650 之间")
        out.append(
            {"name": str(s["name"]).strip()[:20], "ratio": round(float(ratio), 6), "due_days": days}
        )
    if abs(sum(s["ratio"] for s in out) - 1) > 1e-6:
        raise _invalid(f.key, "各期比例合计必须是 100%")
    return out


def _save(
    db: Session, user: CurrentUser, scope: str, changes: dict[str, Any], defaults: dict[str, Any]
) -> None:
    """写入改动：值与默认值相同或为 None 时删除这条改动（恢复默认）。"""
    rows = {
        r.key: r for r in db.scalars(select(ConfigOverride).where(ConfigOverride.scope == scope))
    }
    for key, value in changes.items():
        row = rows.get(key)
        if value is None or value == overrides.get_path(defaults, key):
            if row is not None:
                db.delete(row)
            continue
        if row is None:
            db.add(ConfigOverride(scope=scope, key=key, value=value, updated_by=user.id))
        else:
            row.value, row.updated_by = value, user.id
    db.flush()
    overrides.refresh(db)


def _update(
    db: Session, user: CurrentUser, scope: str, fields: list[SettingField], body: SettingsUpdate
) -> None:
    by_key = {f.key: f for f in fields}
    changes: dict[str, Any] = {}
    for key, value in body.values.items():
        f = by_key.get(key)
        if f is None:
            raise _invalid(key, f"不能在网页上修改：{key}")
        changes[key] = None if value is None else _clean(f, value)
    # 合并后整体再校验一遍（例如规则模型要求的字段）
    candidate = {**overrides.flat(scope), **{k: v for k, v in changes.items() if v is not None}}
    for k in [k for k, v in changes.items() if v is None]:
        candidate.pop(k, None)
    nested: dict[str, Any] = {}
    for k, v in candidate.items():
        overrides.set_path(nested, k, v)
    nested.pop("catalog", None)
    try:
        RuleSet.model_validate(deep_merge(_defaults(scope), nested))
    except ValidationError as exc:
        raise BizError(ErrorCode.VALIDATION, f"配置不完整：{exc.errors()[0]['msg']}") from exc
    _save(db, user, scope, changes, _defaults(scope))


def update_global_settings(db: Session, user: CurrentUser, body: SettingsUpdate) -> SettingsOut:
    _require_admin(user)
    _update(db, user, overrides.GLOBAL, GLOBAL_FIELDS, body)
    return get_global_settings(db, user)


def update_pack_settings(
    db: Session, user: CurrentUser, pack_id: str, body: SettingsUpdate
) -> SettingsOut:
    _require_admin(user)
    _update(db, user, pack_id, _pack_fields(get_pack(pack_id)), body)
    return get_pack_settings(db, user, pack_id)


# ---------- 产品目录 ----------

CATALOG_FIELDS = ("name", "unit", "cost", "price")


class CatalogRow(CatalogItem):
    default_cost: int
    default_price: int
    overridden: bool


class CatalogEdit(BaseModel):
    name: str | None = None
    unit: str | None = None
    cost: int | None = None
    price: int | None = None


def catalog_rows(pack: PackInfo) -> list[CatalogRow]:
    path = pack.path / "catalog.json"
    if not path.exists():
        return []
    defaults = {i.sku: i for i in Catalog.from_file(path).all()}
    edited = overrides.nested(pack.id, "catalog").get("catalog", {})
    return [
        CatalogRow(
            **i.model_dump(),
            default_cost=defaults[i.sku].cost,
            default_price=defaults[i.sku].price,
            overridden=i.sku in edited,
        )
        for i in Catalog.from_file(path, scope=pack.id).all()
    ]


def update_catalog_item(
    db: Session, user: CurrentUser, pack_id: str, sku: str, body: CatalogEdit | None
) -> list[CatalogRow]:
    """改名称 / 单位 / 成本 / 售价（分）；body 为 None 时恢复默认。

    物料的增删依赖配置器的选型逻辑，仍在文件里维护。
    """
    _require_admin(user)
    pack = get_pack(pack_id)
    path = pack.path / "catalog.json"
    items = {i.sku: i for i in Catalog.from_file(path).all()} if path.exists() else {}
    base = items.get(sku)
    if base is None:
        raise BizError(ErrorCode.NOT_FOUND, f"产品不存在：{sku}")
    key = f"catalog.{sku}"
    if body is None:
        _save(db, user, pack_id, {key: None}, {})
        return catalog_rows(pack)
    current = {
        **base.model_dump(),
        **overrides.nested(pack_id, "catalog").get("catalog", {}).get(sku, {}),
    }
    merged = {**current, **body.model_dump(exclude_none=True)}
    if not str(merged["name"]).strip() or not str(merged["unit"]).strip():
        raise _invalid("name", "名称和单位不能为空")
    if merged["cost"] < 0 or merged["price"] <= 0:
        raise _invalid("price", "成本不能为负数，售价必须大于 0")
    diff = {
        f: (str(merged[f]).strip() if f in ("name", "unit") else int(merged[f]))
        for f in CATALOG_FIELDS
        if merged[f] != getattr(base, f)
    }
    _save(db, user, pack_id, {key: diff or None}, {})
    return catalog_rows(pack)


# ---------- 行业包知识库：上传 / 删除 ----------

KB_MAX_BYTES = 10 * 1024 * 1024


def uploaded_dir(pack_id: str) -> Path:
    return uploaded_knowledge_dir(pack_id)


class KnowledgeUploadOut(BaseModel):
    doc_name: str
    chunks: int


def upload_knowledge(
    db: Session, user: CurrentUser, pack_id: str, file_name: str, stream: BinaryIO
) -> KnowledgeUploadOut:
    """保存文档并立即切块、向量化入库；入库失败时不保留文件（避免「看得到但搜不到」）。"""
    _require_admin(user)
    pack = get_pack(pack_id)
    name = Path(file_name or "").name[:120]
    if Path(name).suffix.lower() not in LOADERS:
        raise _invalid("file", "只支持 Markdown（.md）、PDF、Excel（.xlsx）文档")
    content = stream.read(KB_MAX_BYTES + 1)
    if not content:
        raise _invalid("file", "文件为空")
    if len(content) > KB_MAX_BYTES:
        raise _invalid("file", "文档不能超过 10 MB")
    builtin = pack.knowledge_dir / name
    target = uploaded_dir(pack_id) / name
    if builtin.exists() or target.exists():
        raise BizError(ErrorCode.DUPLICATE, f"已有同名文档：{name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    scope = f"pack:{pack_id}"
    try:
        chunks = load_file(target, scope, pack_id)
        existing = set(
            db.scalars(
                select(KbChunk.content_hash).where(
                    KbChunk.content_hash.in_([c.content_hash for c in chunks])
                )
            )
        )
        fresh = dedupe(chunks, existing)
        for start in range(0, len(fresh), EMBED_BATCH):
            batch = fresh[start : start + EMBED_BATCH]
            vectors = embed_texts([embedding_text(c) for c in batch])
            db.add_all(
                KbChunk(
                    scope=c.scope,
                    pack=c.pack,
                    doc_name=c.doc_name,
                    section=c.section,
                    page=c.page,
                    content=c.content,
                    content_hash=c.content_hash,
                    embedding=v,
                )
                for c, v in zip(batch, vectors, strict=True)
            )
        db.flush()
    except BizError:
        target.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise BizError(ErrorCode.UPSTREAM, f"文档入库失败：{exc}") from exc
    if not chunks:
        target.unlink(missing_ok=True)
        raise _invalid("file", "没有从文档里读出内容")
    return KnowledgeUploadOut(doc_name=name, chunks=len(fresh))


def delete_knowledge(db: Session, user: CurrentUser, pack_id: str, doc_name: str) -> None:
    """只能删网页上传的文档（内置文档随代码发布）；同时删掉它在知识库里的切块。"""
    _require_admin(user)
    get_pack(pack_id)
    path = uploaded_dir(pack_id) / Path(doc_name).name
    if not path.is_file():
        raise BizError(ErrorCode.NOT_FOUND, "文档不存在，或是内置文档（不能在网页上删除）")
    db.execute(
        delete(KbChunk).where(KbChunk.scope == f"pack:{pack_id}", KbChunk.doc_name == path.stem)
    )
    path.unlink()


def chunk_counts(db: Session, pack_id: str) -> dict[str, int]:
    stmt = (
        select(KbChunk.doc_name, func.count())
        .where(KbChunk.scope == f"pack:{pack_id}")
        .group_by(KbChunk.doc_name)
    )
    return {name: int(n) for name, n in db.execute(stmt).all()}
