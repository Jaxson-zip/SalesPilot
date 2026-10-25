"""尚未实现的模块：路由已占位，统一返回 501 {"code":50101,"message":"未实现"}。

TODO（照 customers 的写法逐个实现：schema → service → router → 测试）：
- 商机：GET/POST /api/opportunities、PATCH /api/opportunities/{id}/stage、GET /api/pipeline/summary
- 报价：GET /api/quotes、GET /api/quotes/{id}、POST /api/quotes/{id}/submit|send|accept|reject
- 合同：GET /api/contracts、GET /api/contracts/{id}
- 报销：GET/POST /api/expenses
- 审批：GET /api/approvals、POST /api/approvals/{id}/decide（仅 manager）
- 行业包：GET/PUT /api/product-lines（仅 admin）
"""

import uuid

from fastapi import APIRouter

from app.common.auth import CurrentUserDep, Role, require_roles
from app.common.errors import not_implemented
from app.common.response import ApiResponse

opportunities = APIRouter(prefix="/api/opportunities", tags=["opportunities"])
quotes = APIRouter(prefix="/api/quotes", tags=["quotes"])
contracts = APIRouter(prefix="/api/contracts", tags=["contracts"])
expenses = APIRouter(prefix="/api/expenses", tags=["expenses"])
approvals = APIRouter(prefix="/api/approvals", tags=["approvals"])
product_lines = APIRouter(prefix="/api/product-lines", tags=["packs"])

_NOT_IMPL = {501: {"description": "未实现"}}


@opportunities.get("", responses=_NOT_IMPL)
def list_opportunities(user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("opportunities.list")


@opportunities.post("", responses=_NOT_IMPL)
def create_opportunity(user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("opportunities.create")


@opportunities.patch("/{opportunity_id}/stage", responses=_NOT_IMPL)
def change_stage(opportunity_id: uuid.UUID, user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("opportunities.stage")


@quotes.get("", responses=_NOT_IMPL)
def list_quotes(user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("quotes.list")


@quotes.get("/{quote_id}", responses=_NOT_IMPL)
def get_quote(quote_id: uuid.UUID, user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("quotes.get")


@quotes.post("/{quote_id}/submit", responses=_NOT_IMPL)
def submit_quote(quote_id: uuid.UUID, user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("quotes.submit")


@contracts.get("", responses=_NOT_IMPL)
def list_contracts(user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("contracts.list")


@expenses.get("", responses=_NOT_IMPL)
def list_expenses(user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("expenses.list")


@expenses.post("", responses=_NOT_IMPL)
def create_expense(user: CurrentUserDep) -> ApiResponse[None]:
    raise not_implemented("expenses.create")


@approvals.get("", responses=_NOT_IMPL, dependencies=[require_roles(Role.MANAGER)])
def list_approvals() -> ApiResponse[None]:
    raise not_implemented("approvals.list")


@approvals.post(
    "/{approval_id}/decide", responses=_NOT_IMPL, dependencies=[require_roles(Role.MANAGER)]
)
def decide(approval_id: uuid.UUID) -> ApiResponse[None]:
    raise not_implemented("approvals.decide")


@product_lines.get("", responses=_NOT_IMPL, dependencies=[require_roles(Role.ADMIN)])
def list_product_lines() -> ApiResponse[None]:
    raise not_implemented("product_lines.list")


ROUTERS = [opportunities, quotes, contracts, expenses, approvals, product_lines]
