"""行业包配置 service（接口契约 §7）：已安装行业包、产品线 → 行业包映射（仅 admin 可维护）。"""

import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.crm.models import Opportunity, ProductLine
from app.crm.schemas.common import Page
from app.crm.schemas.dashboard import ProductLineItem, ProductLineUpdate
from app.crm.schemas.opportunity import FINAL_STAGES
from app.packs.base import Catalog, CatalogItem
from app.packs.registry import PackInfo, get_pack, list_packs
from app.rag.loaders import LOADERS
from app.rules.loader import load_raw_rules


class PackOut(BaseModel):
    id: str
    name: str
    description: str
    version: str


def list_installed_packs() -> list[PackOut]:
    return [
        PackOut(id=p.id, name=p.name, description=p.description, version=p.version)
        for p in list_packs().values()
    ]


class KnowledgeDoc(BaseModel):
    doc_name: str
    title: str
    size: int  # 字节
    format: str  # 扩展名（不含点），如 md / pdf / xlsx / json
    indexed: bool  # 是否会进入知识库（RAG 支持的格式）；其他文件是行业包的配置数据


class PackDetail(PackOut):
    catalog: list[CatalogItem]
    rules: dict[str, Any]
    knowledge: list[KnowledgeDoc]


def _doc_title(path: Path) -> str:
    """Markdown 取第一个一级 / 二级标题，其他文件用文件名（不含扩展名）。"""
    if path.suffix.lower() == ".md":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip() or path.stem
    return path.stem


def _knowledge(pack: PackInfo) -> list[KnowledgeDoc]:
    if not pack.knowledge_dir.is_dir():
        return []
    files = sorted(p for p in pack.knowledge_dir.iterdir() if p.is_file())
    return [
        KnowledgeDoc(
            doc_name=p.name,
            title=_doc_title(p),
            size=p.stat().st_size,
            format=p.suffix.lower().lstrip("."),
            indexed=p.suffix.lower() in LOADERS,
        )
        for p in files
    ]


def get_pack_detail(pack_id: str) -> PackDetail:
    """行业包只读详情：产品目录（分）、合并后的规则、知识库文档。所有角色可读；未安装 40401。"""
    pack = get_pack(pack_id)
    catalog_file = pack.path / "catalog.json"
    catalog = Catalog.from_file(catalog_file).all() if catalog_file.exists() else []
    return PackDetail(
        id=pack.id,
        name=pack.name,
        description=pack.description,
        version=pack.version,
        catalog=catalog,
        rules=load_raw_rules(pack.rules_file),
        knowledge=_knowledge(pack),
    )


def _require_admin(user: CurrentUser) -> None:
    if user.role is not Role.ADMIN:
        raise BizError(ErrorCode.FORBIDDEN, "仅管理员可以配置行业包")


def _open_counts(db: Session) -> dict[uuid.UUID, int]:
    stmt = (
        select(Opportunity.product_line_id, func.count())
        .where(Opportunity.stage.not_in(FINAL_STAGES), Opportunity.product_line_id.is_not(None))
        .group_by(Opportunity.product_line_id)
    )
    return {pid: int(n) for pid, n in db.execute(stmt).all()}


def _to_item(line: ProductLine, counts: dict[uuid.UUID, int]) -> ProductLineItem:
    return ProductLineItem(
        id=line.id,
        name=line.name,
        pack=line.pack,
        enabled=line.enabled,
        open_opportunities=counts.get(line.id, 0),
    )


def list_product_lines(db: Session, user: CurrentUser) -> Page[ProductLineItem]:
    """所有角色可读（销售建商机时选产品线）；非管理员只看到已启用的。修改仍仅限管理员。"""
    stmt = select(ProductLine).order_by(ProductLine.name)
    if user.role != Role.ADMIN:
        stmt = stmt.where(ProductLine.enabled.is_(True))
    lines = list(db.scalars(stmt).all())
    counts = _open_counts(db)
    return Page[ProductLineItem](items=[_to_item(x, counts) for x in lines], total=len(lines))


def update_product_line(
    db: Session, user: CurrentUser, line_id: uuid.UUID, data: ProductLineUpdate
) -> ProductLineItem:
    _require_admin(user)
    line = db.get(ProductLine, line_id)
    if line is None:
        raise BizError(ErrorCode.NOT_FOUND, "产品线不存在")
    if data.pack is not None:
        if data.pack not in list_packs():
            msg = f"行业包未安装：{data.pack}"
            raise BizError(
                ErrorCode.VALIDATION, msg, {"errors": [{"loc": ["body", "pack"], "msg": msg}]}
            )
        line.pack = data.pack
    if data.enabled is not None:
        line.enabled = data.enabled
    db.flush()
    return _to_item(line, _open_counts(db))
