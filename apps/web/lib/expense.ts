/** 报销表单与票据的纯函数：表单转换、票据齐全判断、上传文件校验 */
import { localDate } from "@/lib/format"
import { parsePositiveInt, yuanToFen } from "@/lib/money"
import type {
  AttachmentKind,
  AttachmentOut,
  ExpenseCreate,
  ExpensePrecheck,
  ExpenseType,
  PolicyCheck,
} from "@/types/api"

export interface ExpenseFormValues {
  type: ExpenseType
  /** 元，字符串 */
  amount: string
  headcount: string
  /** YYYY-MM-DD */
  occurred_on: string
  customer_id: string | null
  participants: string
  reason: string
}

export type FormResult<T> =
  { ok: true; value: T } | { ok: false; errors: Partial<Record<keyof ExpenseFormValues, string>> }

/** 表单 → ExpenseCreate（金额转分；可选字段空串不传） */
export function toExpenseCreate(v: ExpenseFormValues, idempotencyKey?: string): FormResult<ExpenseCreate> {
  const errors: Partial<Record<keyof ExpenseFormValues, string>> = {}
  const amount = yuanToFen(v.amount)
  if (amount === null || amount <= 0) errors.amount = "请输入大于 0 的金额，最多两位小数"
  const headcount = parsePositiveInt(v.headcount, { min: 1, max: 1000 })
  if (headcount === null) errors.headcount = "人数至少为 1"
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.occurred_on)) errors.occurred_on = "请选择发生日期"
  if (!v.reason.trim()) errors.reason = "请填写事由"
  if (v.type === "entertainment" && !v.participants.trim()) errors.participants = "客户招待需写明双方参与人"
  if (amount === null || amount <= 0 || headcount === null || Object.keys(errors).length > 0) {
    return { ok: false, errors }
  }
  const body: ExpenseCreate = {
    type: v.type,
    amount,
    headcount,
    occurred_on: v.occurred_on,
    reason: v.reason.trim(),
  }
  if (v.participants.trim()) body.participants = v.participants.trim()
  if (v.customer_id) body.customer_id = v.customer_id
  if (idempotencyKey) body.idempotency_key = idempotencyKey
  return { ok: true, value: body }
}

/** 实时制度校验的请求体：只要金额、人数、日期、类型合法就可以校验（事由等可以还没填） */
export function toPrecheckBody(v: ExpenseFormValues): ExpenseCreate | null {
  const amount = yuanToFen(v.amount)
  const headcount = parsePositiveInt(v.headcount, { min: 1, max: 1000 })
  if (amount === null || amount <= 0 || headcount === null) return null
  return {
    type: v.type,
    amount,
    headcount,
    occurred_on: v.occurred_on || localDate(),
    reason: v.reason.trim() || "precheck",
  }
}

/** 提交前需要的票据种类（契约 §5：招待需发票 + 小票，其他类型至少一张发票） */
export function requiredKinds(type: ExpenseType): AttachmentKind[] {
  return type === "entertainment" ? ["invoice", "receipt"] : ["invoice"]
}

const KIND_TEXT: Record<AttachmentKind, string> = { invoice: "发票", receipt: "消费小票", other: "其他" }

/** 票据不全时返回原因（用于禁用提交按钮并说明）；齐全返回 null */
export function missingAttachmentReason(type: ExpenseType, attachments: Pick<AttachmentOut, "kind">[]): string | null {
  const have = new Set(attachments.map((a) => a.kind))
  const missing = requiredKinds(type).filter((k) => !have.has(k))
  if (missing.length === 0) return null
  const need = requiredKinds(type)
    .map((k) => KIND_TEXT[k])
    .join("和")
  const prefix = type === "entertainment" ? `客户招待需同时上传${need}` : `需要至少上传一张${need}`
  return `${prefix}，还缺少${missing.map((k) => KIND_TEXT[k]).join("、")}`
}

export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
const ALLOWED_EXT = ["jpg", "jpeg", "png", "pdf"]
const ALLOWED_MIME = ["image/jpeg", "image/png", "application/pdf"]

/** 上传前校验（与 core 一致：jpg / png / pdf，单个 ≤ 10 MB；后端仍会返回 40001） */
export function validateAttachmentFile(file: { name: string; size: number; type: string }): string | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? ""
  if (!ALLOWED_EXT.includes(ext) && !ALLOWED_MIME.includes(file.type)) return `${file.name}：只支持 JPG / PNG / PDF`
  if (file.size > MAX_ATTACHMENT_BYTES) return `${file.name}：超过 10 MB`
  return null
}

/** 文件大小：860 KB / 1.2 MB */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** 统计：「已上传 2 个文件 · 发票 1 · 小票 1」 */
export function attachmentSummary(attachments: Pick<AttachmentOut, "kind">[]): string {
  if (attachments.length === 0) return "还没有上传票据"
  const count = (k: AttachmentKind) => attachments.filter((a) => a.kind === k).length
  const parts = [`发票 ${count("invoice")}`, `小票 ${count("receipt")}`]
  if (count("other")) parts.push(`其他 ${count("other")}`)
  return `已上传 ${attachments.length} 个文件 · ${parts.join(" · ")}`
}

/** 制度校验结果的统一展示结构（precheck 与已保存报销单的 policy_check 字段名不同） */
export interface PolicyCheckView {
  over: boolean
  per_person: number
  limit_per_person: number
  over_amount: number
  /** 后端给出的完整说明（precheck.reason，已含金额），有则直接展示 */
  summary?: string
  /** 补充说明（制度依据） */
  note?: string
}

export function checkFromPrecheck(p: ExpensePrecheck): PolicyCheckView {
  return {
    over: p.need_approval,
    per_person: p.per_person,
    limit_per_person: p.limit_per_person,
    over_amount: p.over_amount,
    summary: p.reason || undefined,
  }
}

export function checkFromPolicy(p: PolicyCheck): PolicyCheckView {
  return {
    over: !p.passed,
    per_person: p.per_person,
    limit_per_person: p.limit_per_person,
    over_amount: p.over_amount,
    note: p.rule_ref ? `依据 ${p.rule_ref}` : undefined,
  }
}
