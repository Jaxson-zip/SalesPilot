/** 客户详情补充（契约 §8）：跟进、联系人、新建客户、客户详情 */
import type { UserBrief } from "@/types/api"
import type { ActivitySource } from "@/types/biz"

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
