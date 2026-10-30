/**
 * 业务模块类型：照抄 docs/api/业务模块接口契约.md（v1）。
 * 金额一律为整数「分」；比例 0–1（win_rate 例外，0–100 整数）；时间 ISO 8601。
 */
import type { ClientCost } from "@/lib/client-costs"
import type { UserBrief } from "@/types/api"
import type { NextTask } from "@/types/biz-v3"

/* ---------- 公共对象（契约 §0） ---------- */
export type DataView = "mine" | "team" | "all"

export interface CustomerBrief {
  id: string
  name: string
}

export interface OppBrief {
  id: string
  name: string
}

export interface ProductLineBrief {
  id: string
  name: string
  pack: string
}

/** system：定时任务等系统操作（没有操作人） */
export type ActivitySource = "manual" | "agent" | "system"

export interface Activity {
  id: string
  subject_type: string
  subject_id: string
  actor: UserBrief | null
  source: ActivitySource
  action: string
  content: string | null
  created_at: string
}

export type AttachmentKind = "invoice" | "receipt" | "other"

export interface AttachmentOut {
  id: string
  kind: AttachmentKind
  file_name: string
  mime: string
  size: number
  url: string
}

/* ---------- 工作台（§1） ---------- */
export interface FunnelStage {
  stage: OpportunityStage
  count: number
  amount: number
}

export interface DashboardData {
  won_amount_month: number
  open_opportunities: number
  open_amount: number
  pending_approvals: number
  estimated_commission_month: number
  confirmed_commission_month: number
  funnel: FunnelStage[]
  /** v3 §12：今天到期 / 已逾期的未完成任务数（后端未就绪时缺省） */
  tasks_today?: number
  tasks_overdue?: number
  /** 当前范围内本月业绩目标之和；没人设目标为 null */
  target_month?: number | null
}

export interface ActivityListParams {
  view: DataView
  subject_type?: string
  subject_id?: string
  limit?: number
}

/* ---------- 商机（§2） ---------- */
export type OpportunityStage = "lead" | "qualified" | "proposal" | "negotiation" | "won" | "lost"

export interface OpportunityItem {
  id: string
  name: string
  customer: CustomerBrief
  stage: OpportunityStage
  amount: number
  /** 0–100 整数 */
  win_rate: number
  expected_close_date: string | null
  product_line: ProductLineBrief | null
  owner: UserBrief | null
  updated_at: string
  /** v3 §12：最早的未完成任务；undefined = 后端还没返回该字段 */
  next_task?: NextTask | null
  /** v3 §13：停滞提醒 */
  last_activity_at?: string | null
  idle_days?: number
  stale?: boolean
  /** 看板卡片：当前阶段应确认却没确认的赢单要素 */
  meddic_risks?: string[]
  /** 看板卡片：标注的竞品名称 */
  competitors?: string[]
}

/** 这单的跟单费用（关联到商机的报销，分） */
export interface OpportunityExpenses {
  /** 已批准 + 已付款 */
  approved: number
  /** 审批中 */
  pending: number
  count: number
}

export interface OpportunityDetail extends OpportunityItem {
  quotes: QuoteItem[]
  activities: Activity[]
  expenses: OpportunityExpenses
}

export interface OpportunityCreate {
  customer_id: string
  name: string
  amount: number
  win_rate?: number
  expected_close_date?: string
  product_line_id?: string
}

/** PATCH /api/opportunities/{id}（U10 行内编辑）：只修改传入的字段 */
export interface OpportunityUpdate {
  name?: string
  amount?: number
  win_rate?: number
  expected_close_date?: string | null
  product_line_id?: string | null
}

export interface StageChange {
  stage: OpportunityStage
  lost_reason?: string
  /** 赢单时按这张报价成交（生成合同、回款计划和提成） */
  quote_id?: string
}

export interface OpportunityListParams {
  view: DataView
  stage?: OpportunityStage
  customer_id?: string
  q?: string
  page?: number
  page_size?: number
}

export interface PipelineSummary {
  stages: FunnelStage[]
  /** 进行中商机（不含赢单、输单）的金额合计 */
  total_amount: number
  weighted_amount: number
  open_count: number
}

/* ---------- 报价单（§3） ---------- */
export type QuoteStatus = "draft" | "pending_approval" | "approved" | "sent" | "accepted" | "rejected"
export type QuoteAction = "submit" | "send" | "accept" | "reject"

export interface QuoteItem {
  id: string
  code: string
  customer: CustomerBrief | null
  opportunity: OppBrief | null
  pack: string
  tier: string
  tier_name: string
  total_price: number
  total_cost: number
  /** 0–1 */
  margin_rate: number
  status: QuoteStatus
  source: ActivitySource
  owner: UserBrief | null
  created_at: string
}

export interface QuoteLine {
  sku: string
  name: string
  unit: string
  qty: number
  unit_cost: number
  unit_price: number
  category: string
  subtotal_cost: number
  subtotal_price: number
}

export type ApprovalStatus = "pending" | "approved" | "rejected"

export interface ApprovalBrief {
  id: string
  status: ApprovalStatus
  reason: string
  approver: UserBrief | null
  comment: string | null
  decided_at: string | null
}

export interface QuoteDetail extends QuoteItem {
  items: QuoteLine[]
  approvals: ApprovalBrief[]
  contract_id: string | null
  estimated_commission: number
  /** v3 §14：整单折扣 0–1；有效期 YYYY-MM-DD（后端未就绪时缺省） */
  discount_rate?: number
  valid_until?: string | null
  /** 运营期客户自付费用（不含在报价内） */
  client_costs?: ClientCost[]
}

export interface QuoteListParams {
  view: DataView
  status?: QuoteStatus
  opportunity_id?: string
  /** 契约未列出；客户详情页需要按客户过滤（见汇报中的疑问） */
  customer_id?: string
  q?: string
  page?: number
  page_size?: number
}

/* ---------- 合同与提成（§4） ---------- */
export type ContractStatus = "active" | "paid"

export interface ContractItem {
  id: string
  code: string
  customer: CustomerBrief | null
  quote: { id: string; code: string } | null
  amount: number
  paid_amount: number
  /** 0–1 */
  paid_ratio: number
  status: ContractStatus
  commission: { estimated: number; confirmed: number }
  owner: UserBrief | null
  created_at: string
  /** 下一期待收款（B9）：第一期没有收齐的；amount 为该期还差的金额。全部收齐时为 null */
  next_payment: NextPayment | null
  /** 已到期未收齐的金额合计 */
  overdue_amount: number
  /** 已申请、等主管开票的期数 */
  invoice_requested?: number
  /** 已开票但还没收齐的金额 */
  invoiced_unpaid_amount?: number
}

/** 回款计划一期的状态：已收齐 / 部分到账（未到期） / 逾期 / 待收 */
export type PlanStatus = "paid" | "partial" | "overdue" | "pending"
/** 开票状态：未开票 / 销售已申请 / 已开票（主管登记） */
export type InvoiceStatus = "none" | "requested" | "issued"
/** 专票 / 普票 */
export type InvoiceType = "special" | "normal"

export interface NextPayment {
  name: string
  amount: number
  due_date: string
  status: PlanStatus
  overdue_days: number
}

/** GET /api/contracts/{id}/payment-plan（实收按期次顺序分摊到各期） */
export interface PaymentPlanItem {
  seq: number
  name: string
  amount: number
  due_date: string
  paid: number
  status: PlanStatus
  overdue_days: number
  invoice_status?: InvoiceStatus
  invoice_type?: InvoiceType | null
  invoice_no?: string | null
  invoiced_on?: string | null
  invoice_note?: string | null
  /** 已开票未收齐：从开票日起算的天数 */
  invoiced_unpaid_days?: number
}

export interface PaymentPlanView {
  contract_id: string
  code: string
  amount: number
  paid_amount: number
  overdue_amount: number
  /** 已开票但还没收齐的金额 */
  invoiced_unpaid_amount?: number
  items: PaymentPlanItem[]
  rule_ref: string
}

/** POST /api/contracts/{id}/payment-plan/{seq}/invoice */
export interface InvoiceIn {
  action: "request" | "issue" | "void"
  invoice_type?: InvoiceType
  invoice_no?: string
  invoiced_on?: string
  note?: string
}

/** PUT /api/contracts/{id}/payment-plan：各期合计必须等于合同金额 */
export interface PaymentPlanUpdate {
  items: { name: string; amount: number; due_date: string }[]
}

export interface ContractSummary {
  month_amount: number
  estimated_commission: number
  confirmed_commission: number
  unpaid_amount: number
}

export interface ContractList {
  items: ContractItem[]
  total: number
  summary: ContractSummary
}

export interface ContractListParams {
  view: DataView
  status?: ContractStatus
  page?: number
  page_size?: number
}

export interface PaymentIn {
  amount: number
}

/* ---------- 报销（§5） ---------- */
export type ExpenseType = "entertainment" | "transport" | "hotel" | "other"
export type ExpenseStatus = "draft" | "pending_approval" | "approved" | "rejected" | "paid"

export interface ExpenseItem {
  id: string
  code: string
  type: ExpenseType
  amount: number
  headcount: number
  occurred_on: string
  customer: CustomerBrief | null
  reason: string | null
  status: ExpenseStatus
  attachment_count: number
  over_limit: boolean
  owner: UserBrief | null
  created_at: string
}

/** v4：差旅交通的行程 / 差旅住宿的城市与入住离店日期（后端 ExpenseDetails） */
export type TransportMode = "train" | "flight" | "taxi" | "bus" | "self_drive" | "other"
export interface ExpenseDetails {
  from_city?: string | null
  to_city?: string | null
  transport_mode?: TransportMode | null
  city?: string | null
  check_in?: string | null
  check_out?: string | null
}

/** unit=night（差旅住宿）时 per_person / limit_per_person 表示每晚金额 */
export type PolicyUnit = "person" | "night"

export interface PolicyCheck {
  passed: boolean
  per_person: number
  limit_per_person: number
  over_amount: number
  rule_ref: string
  unit?: PolicyUnit
}

export interface ExpenseDetail extends ExpenseItem {
  participants: string | null
  opportunity: OppBrief | null
  attachments: AttachmentOut[]
  policy_check: PolicyCheck | null
  /** v3 §17 */
  contacts?: { id: string; name: string; title: string | null }[]
  colleagues?: UserBrief[]
  extra_guests?: number
  details?: ExpenseDetails | null
}

export interface ExpenseCreate {
  type: ExpenseType
  amount: number
  /** v3 §17 起由后端按参与人计算；前端仍传同样算法的结果，兼容旧后端 */
  headcount: number
  occurred_on: string
  participants?: string
  customer_id?: string
  opportunity_id?: string
  reason: string
  idempotency_key?: string
  /** v3 §17：客户方联系人 / 我方同事（不含申请人本人）/ 其他人数 */
  contact_ids?: string[]
  colleague_ids?: string[]
  extra_guests?: number
  details?: ExpenseDetails
}

/** POST /api/expenses/precheck（已有接口，app/rules/calculators.py ExpenseCheck） */
export interface ExpensePrecheck {
  per_person: number
  limit_per_person: number
  over_amount: number
  need_approval: boolean
  reason: string
  unit?: PolicyUnit
  rule_ref?: string
}

export interface ExpenseListParams {
  view: DataView
  status?: ExpenseStatus
  page?: number
  page_size?: number
}

/* ---------- 审批（§6） ---------- */
export type ApprovalTargetType = "quote" | "expense"
export type ApprovalTab = "pending" | "done"
export type ApprovalDecision = "approve" | "reject"

export interface ApprovalItem {
  id: string
  target_type: ApprovalTargetType
  target: {
    id: string
    code: string
    title: string
    amount: number
    owner: UserBrief | null
    /** 报销超出标准的金额（分） */
    over_amount?: number | null
    /** 报价毛利率（0–1） */
    margin_rate?: number | null
    /** 报销发生日期 */
    occurred_on?: string | null
  }
  reason: string
  ai_suggestion: string | null
  status: ApprovalStatus
  attachments: AttachmentOut[]
  comment?: string | null
  decided_at?: string | null
  created_at: string
}

export interface ApprovalDecideIn {
  decision: ApprovalDecision
  comment?: string
}

/* ---------- 行业包配置（§7） ---------- */
export interface ProductLineItem {
  id: string
  name: string
  pack: string
  enabled: boolean
  open_opportunities: number
}

export interface ProductLineUpdate {
  pack?: string
  enabled?: boolean
}

/** GET /api/packs（已有接口，pack_service.PackOut） */
export interface PackOut {
  id: string
  name: string
  description: string
  version: string
  /** 产品目录价格和知识库是演示用的示例资料 */
  sample_data: boolean
}
