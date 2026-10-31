"""报价分享链接（接口契约 §35）：负责人生成 / 查看 / 撤销；甲方凭 token 免登录查看。"""

import uuid

from fastapi import APIRouter

from app.common.auth import CurrentUserDep, OptionalUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.schemas.share import PublicQuote, QuoteShareOut
from app.crm.services import share_service

router = APIRouter(prefix="/api/quotes", tags=["quotes"])
public_router = APIRouter(prefix="/api/public", tags=["public"])
Share = ApiResponse[QuoteShareOut]


@router.post("/{quote_id}/share", response_model=Share)
def create_share(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Share:
    """已审批的报价会同时记为「已发送客户」（不可逆，前端先确认）。"""
    return ok(share_service.create_share(db, user, quote_id))


@router.get("/{quote_id}/share", response_model=ApiResponse[QuoteShareOut | None])
def get_share(
    quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[QuoteShareOut | None]:
    return ok(share_service.get_share(db, user, quote_id))


@router.delete("/{quote_id}/share", response_model=ApiResponse[None])
def revoke_share(quote_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> ApiResponse[None]:
    share_service.revoke_share(db, user, quote_id)
    return ok(None)


@public_router.get("/quotes/{token}", response_model=ApiResponse[PublicQuote])
def public_quote(token: str, db: DbDep, viewer: OptionalUserDep) -> ApiResponse[PublicQuote]:
    """不需要登录：链接无效、撤销、过期都返回 40401。登录着的自己人预览不算客户打开。"""
    return ok(share_service.public_quote(db, token, count_view=viewer is None))
