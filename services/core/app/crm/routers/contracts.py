"""合同与提成接口（接口契约 §4）：列表（含汇总）、详情、登记回款、回款计划与开票跟踪。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, PageDep
from app.crm.schemas.finance import (
    ContractItem,
    ContractList,
    ContractStatus,
    InvoiceIn,
    PaymentIn,
    PaymentPlanUpdate,
    PaymentPlanView,
)
from app.crm.services import contract_service, invoice_service

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


@router.get("/{contract_id}/payment-plan", response_model=ApiResponse[PaymentPlanView])
def get_payment_plan(
    contract_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[PaymentPlanView]:
    """回款计划（B9）：每期金额、到期日、按顺序分摊的实收、是否逾期。"""
    return ok(contract_service.get_payment_plan(db, user, contract_id))


@router.post(
    "/{contract_id}/payment-plan/{seq}/invoice", response_model=ApiResponse[PaymentPlanView]
)
def invoice(
    contract_id: uuid.UUID,
    seq: Annotated[int, Path(ge=1, le=12)],
    body: InvoiceIn,
    user: CurrentUserDep,
    db: DbDep,
) -> ApiResponse[PaymentPlanView]:
    """开票跟踪：负责人申请开票；主管登记已开票或作废。"""
    return ok(invoice_service.act(db, user, contract_id, seq, body))


@router.put("/{contract_id}/payment-plan", response_model=ApiResponse[PaymentPlanView])
def replace_payment_plan(
    contract_id: uuid.UUID, body: PaymentPlanUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[PaymentPlanView]:
    """负责人整体替换回款计划；各期合计必须等于合同金额（42201 plan_total_mismatch）。"""
    return ok(contract_service.replace_payment_plan(db, user, contract_id, body))
