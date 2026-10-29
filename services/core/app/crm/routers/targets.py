"""业绩目标：每人每月签约额目标与完成情况。"""

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import target_service
from app.crm.services.target_service import TargetBoard, TargetUpdate

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.get("", response_model=ApiResponse[TargetBoard])
def get_board(
    user: CurrentUserDep, db: DbDep, month: str | None = None
) -> ApiResponse[TargetBoard]:
    """month=YYYY-MM，默认本月（北京时间）。"""
    return ok(target_service.board(db, user, month))


@router.put("/{month}", response_model=ApiResponse[TargetBoard])
def update_targets(
    month: str, body: TargetUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TargetBoard]:
    """主管批量设置本团队成员的目标（amount 为 null 清除）。"""
    return ok(target_service.update(db, user, month, body))
