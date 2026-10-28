/**
 * 契约 v3 新增类型（docs/api/业务模块接口契约.md §11–§17）。
 * 后端未就绪时相关字段在 biz.ts 里都是可选的，页面显示「后端开发中」。
 */
import type { DataView } from "@/types/biz"
import type { UserBrief } from "@/types/api"

/** 商机列表 / 详情的 next_task（v3 §12） */
export interface NextTask {
  id: string
  title: string
  due_at: string
  overdue: boolean
}

/** PATCH /api/quotes/{id}/items（v3 §14） */
export interface QuoteItemsPatch {
  items: { sku: string; qty: number }[]
  discount_rate: number
}

/* ---------- v3 §11 同事列表 ---------- */
export interface UserItem {
  id: string
  name: string
  role: "sales" | "manager" | "admin"
}

/* ---------- v3 §12 任务与下一步 ---------- */
export type TaskType = "call" | "visit" | "email" | "meeting" | "todo"
export type TaskSubjectType = "customer" | "opportunity"

export interface TaskItem {
  id: string
  title: string
  type: TaskType
  due_at: string
  done: boolean
  done_at: string | null
  note: string | null
  subject_type: TaskSubjectType
  subject_id: string
  subject_name: string | null
  owner: UserBrief | null
  overdue: boolean
}

export interface TaskCreate {
  title: string
  due_at: string
  subject_type: TaskSubjectType
  subject_id: string
  type?: TaskType
  note?: string
}

export interface TaskUpdate {
  title?: string
  due_at?: string
  note?: string
  done?: boolean
}

export interface TaskListParams {
  view: DataView
  status?: "open" | "done"
  due?: "today" | "overdue" | "week"
  subject_type?: TaskSubjectType
  subject_id?: string
}

/* ---------- v3 §15 通知 ---------- */
export type NotificationType = "approval_pending" | "approval_decided" | "customer_assigned" | "task_due"

export interface NotificationItem {
  id: string
  type: NotificationType | string
  title: string
  body: string | null
  link: string | null
  read: boolean
  created_at: string
}

export interface NotificationList {
  items: NotificationItem[]
  total: number
  unread: number
}

/* ---------- v3 §16 转移负责人 ---------- */
export interface CustomerTransferIn {
  customer_ids: string[]
  to_user_id: string
}
