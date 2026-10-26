"""合同、提成、报销、审批 schema（接口契约 §4–§6）。金额单位：分。"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.crm.schemas.common import AttachmentOut, CodeRef, CustomerBrief, OppBrief, UserBrief

# ---------- 合同与提成 ----------

ContractStatus = Literal["active", "paid"]


class CommissionBrief(BaseModel):
    estimated: int
    confirmed: int


class ContractItem(BaseModel):
    id: uuid.UUID
    code: str
    customer: CustomerBrief | None
    quote: CodeRef | None
    amount: int
    paid_amount: int
    paid_ratio: float
    status: ContractStatus
    commission: CommissionBrief
    owner: UserBrief | None
    created_at: datetime


class ContractSummary(BaseModel):
    month_amount: int
    estimated_commission: int
    confirmed_commission: int
    unpaid_amount: int


class ContractList(BaseModel):
    items: list[ContractItem]
    total: int
    summary: ContractSummary


class PaymentIn(BaseModel):
    amount: int = Field(gt=0)


class CommissionLineIn(BaseModel):
    category: Literal["hardware", "software", "service"]
    amount: int = Field(ge=0)


class CommissionEstimateIn(BaseModel):
    lines: list[CommissionLineIn]
    margin_rate: float = Field(ge=-1, le=1)
    paid_ratio: float = Field(default=1.0, ge=0, le=1)


# ---------- 报销 ----------

ExpenseType = Literal["entertainment", "transport", "hotel", "other"]
ExpenseStatus = Literal["draft", "pending_approval", "approved", "rejected", "paid"]
EXPENSE_TYPE_LABELS: dict[str, str] = {
    "entertainment": "客户招待",
    "transport": "差旅交通",
    "hotel": "差旅住宿",
    "other": "其他",
}


TransportMode = Literal["train", "flight", "taxi", "bus", "self_drive", "other"]
TRANSPORT_MODE_LABELS: dict[str, str] = {
    "train": "高铁 / 火车",
    "flight": "飞机",
    "taxi": "出租车 / 网约车",
    "bus": "公交 / 地铁",
    "self_drive": "自驾",
    "other": "其他",
}


class ExpenseDetails(BaseModel):
    """按类型填写的补充信息（v4）：差旅交通填行程，差旅住宿填城市和入住 / 离店日期。"""

    model_config = ConfigDict(extra="forbid")

    from_city: str | None = Field(default=None, max_length=50)
    to_city: str | None = Field(default=None, max_length=50)
    transport_mode: TransportMode | None = None
    city: str | None = Field(default=None, max_length=50)
    check_in: date | None = None
    check_out: date | None = None


class ExpensePrecheckIn(BaseModel):
    """不落库的制度校验（POST /api/expenses/precheck）。"""

    type: ExpenseType = "entertainment"
    amount: int = Field(gt=0)
    headcount: int = Field(default=1, ge=1, le=1000)
    occurred_on: date | None = None
    details: ExpenseDetails | None = None


class ExpenseCreate(BaseModel):
    """v3 §17：headcount / participants 由后端按参与人计算（客户端传入的被忽略，仅为兼容保留）。"""

    type: ExpenseType
    amount: int = Field(gt=0)
    headcount: int | None = Field(default=None, ge=1, le=1000)
    occurred_on: date
    participants: str | None = Field(default=None, max_length=500)
    contact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    colleague_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    extra_guests: int = Field(default=0, ge=0, le=500)
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    details: ExpenseDetails | None = None


class PolicyCheck(BaseModel):
    passed: bool
    per_person: int  # unit=night 时为每晚金额
    limit_per_person: int
    over_amount: int
    rule_ref: str
    unit: Literal["person", "night"] = "person"


class ExpenseItem(BaseModel):
    id: uuid.UUID
    code: str
    type: ExpenseType
    amount: int
    headcount: int
    occurred_on: date
    customer: CustomerBrief | None
    reason: str | None
    status: ExpenseStatus
    attachment_count: int
    over_limit: bool
    owner: UserBrief | None
    created_at: datetime


class ContactBrief(BaseModel):
    id: uuid.UUID
    name: str
    title: str | None


class ExpenseDetail(ExpenseItem):
    participants: str | None
    contacts: list[ContactBrief]
    colleagues: list[UserBrief]
    extra_guests: int
    opportunity: OppBrief | None
    attachments: list[AttachmentOut]
    policy_check: PolicyCheck | None
    details: ExpenseDetails | None = None


# ---------- 审批 ----------

ApprovalStatus = Literal["pending", "approved", "rejected"]


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


class ApprovalTarget(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    amount: int
    owner: UserBrief | None


class ApprovalItem(BaseModel):
    id: uuid.UUID
    target_type: Literal["quote", "expense"]
    target: ApprovalTarget
    reason: str
    ai_suggestion: str | None
    status: ApprovalStatus
    attachments: list[AttachmentOut]
    comment: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
