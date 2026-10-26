"""纯规则接口（不依赖数据库）：行业包列表、提成估算、报销制度预校验。"""

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.schemas.finance import CommissionEstimateIn, ExpensePrecheckIn
from app.crm.services import finance_service, pack_service
from app.crm.services.pack_service import PackOut
from app.rules import CommissionResult, ExpenseCheck

router = APIRouter(prefix="/api", tags=["rules"])


@router.get("/packs", response_model=ApiResponse[list[PackOut]])
def list_packs(user: CurrentUserDep) -> ApiResponse[list[PackOut]]:
    return ok(pack_service.list_installed_packs())


@router.post("/commissions/estimate", response_model=ApiResponse[CommissionResult])
def estimate_commission(
    body: CommissionEstimateIn, user: CurrentUserDep
) -> ApiResponse[CommissionResult]:
    return ok(finance_service.estimate_commission(body))


@router.post("/expenses/precheck", response_model=ApiResponse[ExpenseCheck])
def precheck_expense(body: ExpensePrecheckIn, user: CurrentUserDep) -> ApiResponse[ExpenseCheck]:
    return ok(finance_service.precheck_expense(body))
