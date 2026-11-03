"""合同与提成接口（接口契约 §4）：列表（含汇总）、详情、登记回款、回款计划与开票跟踪。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, Ids, Multi, PageDep
from app.crm.schemas.finance import (
    ContractItem,
    ContractList,
    ContractStatus,
    InvoiceIn,
    PaymentIn,
    PaymentPlanUpdate,
    PaymentPlanView,
    PaymentRecord,
    PaymentReverseIn,
)
from app.crm.services import (
    contract_service,
    invoice_service,
    payment_plan_change,
    payment_service,
)
from app.crm.services.contract_service import ContractFilter
from app.crm.services.listing import FacetOption, SortKey, clean, uuids

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _filter(
    status_in: Multi = None,
    overdue: Multi = None,
    customer_in: Ids = None,
    owner_in: Ids = None,
    sort: SortKey | None = None,
) -> ContractFilter:
    return ContractFilter(
        clean(status_in), clean(overdue), uuids(customer_in), uuids(owner_in), sort
    )


@router.get("", response_model=ApiResponse[ContractList])
def list_contracts(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    f: Annotated[ContractFilter, Depends(_filter)],
    view: View | None = None,
    status: ContractStatus | None = None,
) -> ApiResponse[ContractList]:
    """status 是页签；status_in / overdue / customer_in / owner_in 是筛选（多选）。"""
    return ok(contract_service.list_contracts(db, user, view, page, status, f))


@router.get("/facets", response_model=ApiResponse[dict[str, list[FacetOption]]])
def contract_facets(
    user: CurrentUserDep, db: DbDep, view: View | None = None
) -> ApiResponse[dict[str, list[FacetOption]]]:
    """列表筛选项：当前范围内出现过的客户、负责人。"""
    return ok(contract_service.facets(db, user, view))


@router.get("/{contract_id}", response_model=ApiResponse[ContractItem])
def get_contract(
    contract_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ContractItem]:
    return ok(contract_service.get_contract(db, user, contract_id))


@router.post("/{contract_id}/payments", response_model=ApiResponse[ContractItem])
def add_payment(
    contract_id: uuid.UUID, body: PaymentIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ContractItem]:
    return ok(payment_service.add_payment(db, user, contract_id, body))


@router.get("/{contract_id}/payments", response_model=ApiResponse[list[PaymentRecord]])
def list_payments(
    contract_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ApiResponse[list[PaymentRecord]]:
    return ok(payment_service.list_payments(db, user, contract_id))


@router.post(
    "/{contract_id}/payments/{payment_id}/reverse", response_model=ApiResponse[ContractItem]
)
def reverse_payment(
    contract_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: PaymentReverseIn,
    user: CurrentUserDep,
    db: DbDep,
) -> ApiResponse[ContractItem]:
    return ok(payment_service.reverse_payment(db, user, contract_id, payment_id, body.reason))


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
    """负责人整体替换回款计划（42201）：合计须等于合同金额（plan_total_mismatch）；
    已收款 / 已开票的期次锁定（plan_paid_locked / plan_invoiced）；
    已有回款、逾期或开票时须写原因（plan_reason_required）。"""
    return ok(payment_plan_change.replace_payment_plan(db, user, contract_id, body))
