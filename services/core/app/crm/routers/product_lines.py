"""行业包配置接口（接口契约 §7，仅 admin；角色校验在 pack_service）。"""

import uuid

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.schemas.common import Page
from app.crm.schemas.dashboard import ProductLineItem, ProductLineUpdate
from app.crm.services import pack_service

router = APIRouter(prefix="/api/product-lines", tags=["packs"])


@router.get("", response_model=ApiResponse[Page[ProductLineItem]])
def list_product_lines(user: CurrentUserDep, db: DbDep) -> ApiResponse[Page[ProductLineItem]]:
    return ok(pack_service.list_product_lines(db, user))


@router.put("/{line_id}", response_model=ApiResponse[ProductLineItem])
def update_product_line(
    line_id: uuid.UUID, body: ProductLineUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ProductLineItem]:
    return ok(pack_service.update_product_line(db, user, line_id, body))
