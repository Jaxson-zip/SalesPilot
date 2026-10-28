"""AI 用量与成本统计（管理员全公司 / 主管本团队）。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import usage_service
from app.crm.services.usage_service import Period, UsageStats

router = APIRouter(prefix="/api/ai-usage", tags=["ai-usage"])


@router.get("", response_model=ApiResponse[UsageStats])
def ai_usage(
    user: CurrentUserDep, db: DbDep, period: Annotated[Period, Query()] = "30d"
) -> ApiResponse[UsageStats]:
    return ok(usage_service.stats(db, user, period))
