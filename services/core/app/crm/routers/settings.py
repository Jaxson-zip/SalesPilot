"""网页上维护的配置（仅管理员）：通用业务规则、行业包参数、产品价格、行业包知识库文档。"""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import catalog_service, settings_service
from app.crm.services.catalog_service import CatalogEdit, CatalogRow
from app.crm.services.settings_service import (
    KnowledgeUploadOut,
    SettingsOut,
    SettingsUpdate,
)

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings/rules", response_model=ApiResponse[SettingsOut])
def get_rules(user: CurrentUserDep, db: DbDep) -> ApiResponse[SettingsOut]:
    return ok(settings_service.get_global_settings(db, user))


@router.put("/settings/rules", response_model=ApiResponse[SettingsOut])
def update_rules(body: SettingsUpdate, user: CurrentUserDep, db: DbDep) -> ApiResponse[SettingsOut]:
    return ok(settings_service.update_global_settings(db, user, body))


@router.get("/packs/{pack_id}/settings", response_model=ApiResponse[SettingsOut])
def get_pack_settings(pack_id: str, user: CurrentUserDep, db: DbDep) -> ApiResponse[SettingsOut]:
    return ok(settings_service.get_pack_settings(db, user, pack_id))


@router.put("/packs/{pack_id}/settings", response_model=ApiResponse[SettingsOut])
def update_pack_settings(
    pack_id: str, body: SettingsUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[SettingsOut]:
    return ok(settings_service.update_pack_settings(db, user, pack_id, body))


@router.put("/packs/{pack_id}/catalog/{sku}", response_model=ApiResponse[list[CatalogRow]])
def update_catalog_item(
    pack_id: str, sku: str, body: CatalogEdit, user: CurrentUserDep, db: DbDep
) -> ApiResponse[list[CatalogRow]]:
    return ok(catalog_service.update_catalog_item(db, user, pack_id, sku, body))


@router.delete("/packs/{pack_id}/catalog/{sku}", response_model=ApiResponse[list[CatalogRow]])
def reset_catalog_item(
    pack_id: str, sku: str, user: CurrentUserDep, db: DbDep
) -> ApiResponse[list[CatalogRow]]:
    return ok(catalog_service.update_catalog_item(db, user, pack_id, sku, None))


@router.post("/packs/{pack_id}/knowledge", response_model=ApiResponse[KnowledgeUploadOut])
def upload_knowledge(
    pack_id: str, user: CurrentUserDep, db: DbDep, file: Annotated[UploadFile, File()]
) -> ApiResponse[KnowledgeUploadOut]:
    return ok(settings_service.upload_knowledge(db, user, pack_id, file.filename or "", file.file))


@router.delete("/packs/{pack_id}/knowledge/{doc_name}", response_model=ApiResponse[None])
def delete_knowledge(
    pack_id: str, doc_name: str, user: CurrentUserDep, db: DbDep
) -> ApiResponse[None]:
    settings_service.delete_knowledge(db, user, pack_id, doc_name)
    return ok(None)
