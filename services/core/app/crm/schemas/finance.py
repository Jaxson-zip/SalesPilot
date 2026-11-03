"""合同、提成、报销、审批 schema（接口契约 §4–§6）。金额单位：分。"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.crm.schemas.common import AttachmentOut, CodeRef, CustomerBrief, OppBrief, UserBrief
from app.crm.schemas.fields import ExpenseReason, PastDate, PlanName
from app.crm.schemas.quote import ApprovalBrief

# ---------- 合同与提成 ----------

ContractStatus = Literal["active", "paid"]


class CommissionBrief(BaseModel):
    estimated: int
    confirmed: int


PlanStatus = Literal["paid", "partial", "overdue", "pending"]
InvoiceStatus = Literal["none", "requested", "issued"]
InvoiceType = Literal["special", "normal"]


class NextPayment(BaseModel):
    """下一期待收款（合同列表用）：第一期没有收齐的。amount 为该期还差的金额。"""

    name: str
    amount: int
    due_date: date
    status: PlanStatus
    overdue_days: int


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
    next_payment: NextPayment | None = None
    overdue_amount: int = 0  # 已到期未收齐的金额合计
    invoice_requested: int = 0  # 已申请、等主管开票的期数
    invoiced_unpaid_amount: int = 0  # 已开票但还没收齐的金额


class PaymentPlanItem(BaseModel):
    seq: int
    name: str
    amount: int
    due_date: date
    paid: int  # 实收按期次顺序分摊到这一期的金额
    status: PlanStatus
    overdue_days: int
    invoice_status: InvoiceStatus = "none"
    invoice_type: InvoiceType | None = None
    invoice_no: str | None = None
    invoiced_on: date | None = None
    invoice_note: str | None = None
    invoiced_unpaid_days: int = 0  # 已开票未收齐：从开票日起算的天数


class InvoiceEventOut(BaseModel):
    """开票历史一条：作废时 invoice_no / invoiced_on 是被作废的原票，note 是作废原因。"""

    seq: int
    plan_name: str
    amount: int
    action: Literal["request", "issue", "void"]
    from_status: InvoiceStatus
    invoice_type: InvoiceType | None
    invoice_no: str | None
    invoiced_on: date | None
    note: str | None
    actor: UserBrief | None
    created_at: datetime


class PaymentPlanView(BaseModel):
    contract_id: uuid.UUID
    code: str
    amount: int
    paid_amount: int
    overdue_amount: int
    invoiced_unpaid_amount: int = 0  # 已开票但还没收齐的金额
    items: list[PaymentPlanItem]
    rule_ref: str
    invoice_events: list[InvoiceEventOut] = []  # 开票历史，新的在前


class InvoiceIn(BaseModel):
    """开票操作：request 负责人申请；issue 主管登记已开票；void 主管作废（红冲或撤回申请）。"""

    action: Literal["request", "issue", "void"]
    invoice_type: InvoiceType | None = None
    invoice_no: str | None = Field(default=None, max_length=50)
    invoiced_on: date | None = None
    note: str | None = Field(default=None, max_length=200)


class PaymentPlanLineIn(BaseModel):
    name: PlanName
    amount: int = Field(gt=0)
    due_date: date


class PaymentPlanUpdate(BaseModel):
    items: list[PaymentPlanLineIn] = Field(min_length=1, max_length=12)


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
    # 对账信息：到账日期（不传按今天）、银行流水号 / 交易单号、备注
    received_on: PastDate | None = None
    reference_no: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=200)
    # 同一次登记的重试带同一个键（前端每次打开登记框生成一个）：第一次已入账就不再记一笔
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class PaymentReverseIn(BaseModel):
    """冲正一笔登记错的回款：原记录保留，另记一笔负数，必须写原因。"""

    reason: str = Field(min_length=2, max_length=200)


class PaymentRecord(BaseModel):
    id: uuid.UUID
    amount: int  # 冲正记录为负数
    received_on: date
    reference_no: str | None
    note: str | None
    reversal_of: uuid.UUID | None  # 冲正的是哪一笔
    reversed_by: uuid.UUID | None = None  # 这笔被哪条冲正记录冲掉了
    reason: str | None
    created_by: UserBrief | None
    created_at: datetime


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
    occurred_on: PastDate
    participants: str | None = Field(default=None, max_length=500)
    contact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    colleague_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    extra_guests: int = Field(default=0, ge=0, le=500)
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    reason: ExpenseReason
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    details: ExpenseDetails | None = None


class ExpenseBasics(BaseModel):
    """提交前复核用：事由去掉空格后必填、发生日期不晚于今天（和新建 / 修改同一套校验）。"""

    reason: ExpenseReason
    occurred_on: PastDate


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
    # 审批记录（驳回原因看最后一条）
    approvals: list[ApprovalBrief] = []


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
    # 审批时最关心的数字：报销超出标准多少（分）、报价毛利率；发生日期
    over_amount: int | None = None
    margin_rate: float | None = None
    occurred_on: date | None = None


class ApprovalItem(BaseModel):
    id: uuid.UUID
    target_type: Literal["quote", "expense"]
    target: ApprovalTarget
    reason: str
    ai_suggestion: str | None
    # 关联商机的当前状态（实时）；审批建议是提交时写的，商机之后可能已输单
    deal_note: str | None = None
    status: ApprovalStatus
    attachments: list[AttachmentOut]
    comment: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
