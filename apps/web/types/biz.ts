/**
 * 业务模块类型：照抄 docs/api/业务模块接口契约.md（v1）。
 * 金额一律为整数「分」；比例 0–1（win_rate 例外，0–100 整数）；时间 ISO 8601。
 */
import type { UserBrief } from "@/types/api"

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

export type ActivitySource = "manual" | "agent"

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
  owner: UserBrief
  updated_at: string
}

export interface OpportunityDetail extends OpportunityItem {
  quotes: QuoteItem[]
  activities: Activity[]
}

export interface OpportunityCreate {
  customer_id: string
  name: string
  amount: number
  win_rate?: number
  expected_close_date?: string
  product_line_id?: string
}

export interface StageChange {
  stage: OpportunityStage
  lost_reason?: string
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
  total_amount: number
  weighted_amount: number
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
  owner: UserBrief
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
  owner: UserBrief
  created_at: string
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
  reason: string
  status: ExpenseStatus
  attachment_count: number
  over_limit: boolean
  owner: UserBrief
  created_at: string
}

export interface PolicyCheck {
  passed: boolean
  per_person: number
  limit_per_person: number
  over_amount: number
  rule_ref: string
}

export interface ExpenseDetail extends ExpenseItem {
  participants: string | null
  opportunity: OppBrief | null
  attachments: AttachmentOut[]
  policy_check: PolicyCheck
}

export interface ExpenseCreate {
  type: ExpenseType
  amount: number
  headcount: number
  occurred_on: string
  participants?: string
  customer_id?: string
  opportunity_id?: string
  reason: string
  idempotency_key?: string
}

/** POST /api/expenses/precheck（已有接口，app/rules/calculators.py ExpenseCheck） */
export interface ExpensePrecheck {
  per_person: number
  limit_per_person: number
  over_amount: number
  need_approval: boolean
  reason: string
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
  target: { id: string; code: string; title: string; amount: number; owner: UserBrief }
  reason: string
  ai_suggestion: string | null
  status: ApprovalStatus
  attachments: AttachmentOut[]
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
}

/* ---------- 客户详情补充（§8） ---------- */
export type FollowupType = "phone" | "visit" | "wechat" | "email"

/** 契约未给出返回结构，与 core schemas/dashboard.py FollowupItem 对齐（owner 为前端期望的可选字段） */
export interface FollowupItem {
  id: string
  customer_id?: string
  opportunity_id?: string | null
  type: FollowupType | "ai"
  content: string
  source: ActivitySource
  occurred_at: string | null
  created_at: string
  owner?: UserBrief | null
}

export interface FollowupCreate {
  type: FollowupType
  content: string
  occurred_at?: string
  opportunity_id?: string
}

/** 契约未给出返回结构，按 contacts 表字段约定（见汇报） */
export interface ContactItem {
  id: string
  name: string
  title: string | null
  phone: string | null
  is_decision_maker: boolean
}

/** POST /api/customers（core schemas/customer.py CustomerCreate；annual_budget 单位：分） */
export type CustomerLevel = "A" | "B" | "C"

export interface CustomerCreate {
  name: string
  industry?: string
  level?: CustomerLevel
  size?: string
  address?: string
  website?: string
  annual_budget?: number
  tags?: string[]
}

/** GET /api/customers/{id}（已有接口，CustomerDetail） */
export interface CustomerDetail {
  id: string
  name: string
  industry: string | null
  level: string
  owner: UserBrief | null
  website: string | null
  opportunity_amount: number
  last_followup_at: string | null
  size: string | null
  address: string | null
  annual_budget: number | null
  tags: string[]
  created_at: string
}
