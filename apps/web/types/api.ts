/**
 * 接口类型（先手写，与 docs/开发规范.md §8 保持一致）。
 * TODO: docs/api/openapi.yaml 就绪后改为 openapi-typescript 自动生成。
 */

import type { ClientCost } from "@/lib/client-costs"

/** 统一响应 §8.1 */
export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  request_id: string
}

/** 错误码 §8.2 */
export const ErrorCode = {
  OK: 0,
  VALIDATION: 40001,
  MODEL_CAPABILITY: 40002,
  UNAUTHORIZED: 40101,
  FORBIDDEN: 40301,
  NOT_FOUND: 40401,
  DUPLICATE: 40901,
  BIZ_RULE: 42201,
  RATE_LIMITED: 42901,
  INTERNAL: 50001,
  /** 接口已占位、尚未实现（HTTP 501） */
  NOT_IMPLEMENTED: 50101,
  GATEWAY_UPSTREAM: 50201,
  GATEWAY_TIMEOUT: 50401,
  /** 前端自定义：网络不可达（core 未启动等），不会出现在后端响应里 */
  NETWORK: -1,
} as const
export type ErrorCodeValue = (typeof ErrorCode)[keyof typeof ErrorCode]

export interface Paged<T> {
  items: T[]
  total: number
}

/* ---------- 认证 ---------- */
export type Role = "sales" | "manager" | "admin"

export interface UserBrief {
  id: string
  name: string
}

export interface CurrentUser extends UserBrief {
  role: Role
  team_id?: string | null
  team_name?: string | null
  /** 登录名（演示数据未导入时为空） */
  username?: string | null
  /** 管理员新建 / 重置密码后为 true：先改密码 */
  must_change_password?: boolean
  /** 个人模式（业务规则 org.solo_mode）：隐藏团队相关页面，主管可以改系统配置 */
  solo_mode?: boolean
}

export interface MockLoginRequest {
  role: Role
}

export interface MockLoginData {
  token: string
  user?: CurrentUser
}

/* ---------- 客户 ---------- */
export type CustomerView = "mine" | "team" | "all"

export interface Customer {
  id: string
  name: string
  industry: string | null
  level: string
  owner: UserBrief | null
  website: string | null
  /** 单位：分 */
  opportunity_amount: number
  /** ISO 8601 */
  last_followup_at: string | null
}

export interface CustomerListParams {
  view: CustomerView
  page: number
  page_size: number
}

/* ---------- Agent ---------- */
export interface AgentChatRequest {
  thread_id: string
  message: string
  model: string
}

export type ResumeDecision = "approve" | "reject"

/** GET /api/agent/models：网关里支持工具调用的模型 / 分组，以及是否已配置 Key */
export interface ChatModel {
  id: string
  type: "model" | "group"
  available: boolean
  members: string[]
}
export interface ChatModels {
  items: ChatModel[]
  default: string
  any_available: boolean
  gateway_ok: boolean
}

export interface AgentResumeRequest {
  thread_id: string
  decision: ResumeDecision
  /** 确认生成报价单时另选的档位（tier 键）；不传按推荐档 */
  tier?: string
}

/** §8.3 SSE 事件 */
export interface AgentEventMap {
  "node.start": { node: string }
  "tool.start": { call_id: string; name: string; args: Record<string, unknown> }
  "tool.end": { call_id: string; summary: string; result?: unknown }
  "tool.error": { call_id: string; code: number; message: string }
  "node.retry": { node: string; reason: string; attempt: number }
  interrupt: { action: string; preview: Record<string, unknown> }
  artifact: { type: string; data: unknown }
  "message.delta": { text: string }
  /** 用一段文字替换当前正文（确认后写操作已完成，模型却还在让用户确认时，按执行结果改正） */
  "message.replace": { text: string }
  done: { thread_id: string }
  error: { code: number; message: string }
}

export type AgentEventName = keyof AgentEventMap

export type AgentEvent = {
  [K in AgentEventName]: { event: K; data: AgentEventMap[K] }
}[AgentEventName]

/* ---------- Agent 结构化产物（artifact.data） ---------- */
export interface SolutionTier {
  name: string
  spec: string
  /** 单位：分 */
  price: number
  /** 0–1 */
  margin: number
  recommended?: boolean
  /** 档位键（core 的 tier，如 economy）；有键才能在对话里点选 */
  key?: string
}

export interface BomItem {
  name: string
  quantity: string
  /** 单位：分 */
  cost: number
  /** 单位：分 */
  price: number
}

export interface BomData {
  title: string
  items: BomItem[]
  totals: { label: string; value: string }[]
  /** 运营期客户自付费用（不含在报价内） */
  client_costs?: ClientCost[]
}

export interface SourceRef {
  title: string
  url?: string
}

/* ---------- 业务模块（商机 · 报价 · 合同 · 报销 · 审批 · 工作台 · 行业包） ---------- */
export * from "@/types/biz"
export * from "@/types/biz-customer"
export * from "@/types/biz-v3"
export * from "@/types/biz-v4"
