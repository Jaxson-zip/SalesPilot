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
  opportunity_name?: string | null
  /** 这次跟进联系的是谁（联系人删除后为空） */
  contact_id?: string | null
  contact_name?: string | null
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
  contact_id?: string
}

/** 联系人在采购决策中的角色（B7，对应 Salesforce 的 Contact Role） */
export type ContactRole = "decision_maker" | "influencer" | "technical" | "finance" | "user"

/** GET /api/customers/{id}/contacts（按角色重要程度排序） */
export interface ContactItem {
  id: string
  name: string
  title: string | null
  /** 脱敏后的号码（139****2222）；完整号码点「查看」获取，会记入操作日志 */
  phone: string | null
  has_phone?: boolean
  /** 由 role 派生：role === "decision_maker" */
  is_decision_maker: boolean
  role: ContactRole | null
}

/** POST /api/customers/{id}/contacts；PATCH 时全部字段可选 */
export interface ContactIn {
  name: string
  title?: string | null
  phone?: string | null
  role?: ContactRole | null
}
export type ContactUpdate = Partial<ContactIn>

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

/** PATCH /api/customers/{id}（U10 行内编辑）：只修改传入的字段；annual_budget 单位：分 */
export interface CustomerUpdate {
  name?: string
  industry?: string | null
  level?: CustomerLevel
  size?: string | null
  address?: string | null
  website?: string | null
  annual_budget?: number | null
}

/** POST /api/customers/{id}/release：退回公海（B5） */
export interface PoolRelease {
  reason: string
}

/** GET /api/customers/similar：新建客户查重。看不到的客户 id 为 null，只给名称和负责人 */
export interface SimilarCustomer {
  id: string | null
  name: string
  owner_name: string | null
  /** 去掉「有限公司」「（深圳）」等后名称相同：后端会拒绝创建 */
  exact: boolean
  visible: boolean
}
