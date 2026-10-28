"""网页上改过的配置（config_overrides 表）的进程内快照。

规则、产品目录在很多地方同步读取（报价、报销、Agent 工具……），不能每次都查库：
启动时和每次保存后从数据库刷新一次，读取时直接用内存里的快照。
core 以单进程运行（Dockerfile 里 uvicorn 没有 --workers），保存后立即对所有请求生效。
"""

import copy
import logging
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("core.rules")

GLOBAL = "global"

_lock = threading.Lock()
# scope → {点分 key → value}
_flat: dict[str, dict[str, Any]] = {}


def set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    """按点分路径写入嵌套字典：set_path(d, "commission.rates.hardware", 0.03)。"""
    *parents, last = dotted.split(".")
    node = target
    for part in parents:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[last] = value


def get_path(source: dict[str, Any], dotted: str) -> Any:
    node: Any = source
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def flat(scope: str) -> dict[str, Any]:
    """该范围内改过的项（点分 key → 值）。"""
    with _lock:
        return copy.deepcopy(_flat.get(scope, {}))


def nested(scope: str, prefix: str = "") -> dict[str, Any]:
    """改过的项展开成嵌套字典，用来覆盖规则文件；prefix 只取某一段（如 catalog）。"""
    out: dict[str, Any] = {}
    for key, value in flat(scope).items():
        if prefix and not key.startswith(prefix + "."):
            continue
        set_path(out, key, value)
    return out


def replace(rows: dict[str, dict[str, Any]]) -> None:
    with _lock:
        _flat.clear()
        _flat.update(copy.deepcopy(rows))


def refresh(db: Session) -> None:
    """从数据库重新读取全部改动（启动时、保存后调用）。"""
    from app.crm.models import ConfigOverride

    rows: dict[str, dict[str, Any]] = {}
    for row in db.scalars(select(ConfigOverride)):
        rows.setdefault(row.scope, {})[row.key] = row.value
    replace(rows)
    logger.info("config overrides loaded: %s", {s: len(v) for s, v in rows.items()})


def refresh_on_startup() -> None:
    from app.common.db import session_scope

    try:
        with session_scope() as db:
            refresh(db)
    except Exception:
        logger.warning("config overrides unavailable, using file defaults", exc_info=True)
