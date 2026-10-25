/**
 * 接口类型（先手写，与 docs/开发规范.md §8 保持一致）。
 * TODO: docs/api/openapi.yaml 就绪后改为 openapi-typescript 自动生成。
 */

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
  industry: string
  level: string
  owner: UserBrief
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

export interface AgentResumeRequest {
  thread_id: string
  decision: ResumeDecision
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
}

export interface SourceRef {
  title: string
  url?: string
}
