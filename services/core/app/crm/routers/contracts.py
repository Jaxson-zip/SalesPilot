"""合同与提成接口（接口契约 §4）：列表（含汇总）、详情、登记回款。"""

import uuid

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, PageDep
from app.crm.schemas.finance import ContractItem, ContractList, ContractStatus, PaymentIn
from app.crm.services import contract_service

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.get("", response_model=ApiResponse[ContractList])
def list_contracts(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    view: View | None = None,
    status: ContractStatus | None = None,
) -> ApiResponse[ContractList]:
    return ok(contract_service.list_contracts(db, user, view, page, status))


@router.get("/{contract_id}", response_model=ApiResponse[ContractItem])
def get_contract(
    contract_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ContractItem]:
    return ok(contract_service.get_contract(db, user, contract_id))


@router.post("/{contract_id}/payments", response_model=ApiResponse[ContractItem])
def add_payment(
    contract_id: uuid.UUID, body: PaymentIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ContractItem]:
    return ok(contract_service.add_payment(db, user, contract_id, body.amount))
