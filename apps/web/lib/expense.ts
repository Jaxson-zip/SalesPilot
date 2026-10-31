/** 报销表单与票据的纯函数：表单转换、票据齐全判断、上传文件校验 */
import { toDetails, tripErrors, type TripErrors, type TripValues } from "@/lib/expense-trip"
import { formatFen, localDate } from "@/lib/format"
import { fenToYuanInput, parsePositiveInt, yuanToFen } from "@/lib/money"
import type {
  ApprovalBrief,
  AttachmentKind,
  AttachmentOut,
  ExpenseCreate,
  ExpenseDetail,
  ExpensePrecheck,
  ExpenseType,
  PolicyCheck,
  PolicyUnit,
} from "@/types/api"

export interface ExpenseFormValues {
  type: ExpenseType
  /** 元，字符串 */
  amount: string
  /** YYYY-MM-DD */
  occurred_on: string
  customer_id: string | null
  opportunity_id: string | null
  /** 客户方参与人（所关联客户的联系人） */
  contact_ids: string[]
  /** 我方参与人（本团队同事，不含申请人本人——本人始终算在内） */
  colleague_ids: string[]
  /** 其他人数（字符串，空 = 0） */
  extra_guests: string
  reason: string
  /** v4：差旅交通的行程 / 差旅住宿的城市和日期 */
  trip: TripValues
}

export type ExpenseFormErrors = Partial<Record<Exclude<keyof ExpenseFormValues, "trip">, string>> & TripErrors

export type FormResult<T> = { ok: true; value: T } | { ok: false; errors: ExpenseFormErrors }

/** 其他人数：空串 = 0；非法 → null */
export function parseExtraGuests(input: string): number | null {
  if (!input.trim()) return 0
  return parsePositiveInt(input, { min: 0, max: 999 })
}

/**
 * 总人数（契约 v3 §17，与后端同一算法）= 客户方联系人 + 我方同事 + 申请人本人 + 其他人数。
 * 其他人数非法时按 0 计。
 */
export function participantCount(v: Pick<ExpenseFormValues, "contact_ids" | "colleague_ids" | "extra_guests">): number {
  return v.contact_ids.length + v.colleague_ids.length + 1 + (parseExtraGuests(v.extra_guests) ?? 0)
}

/** 人均（分，四舍五入）；只用于表单上的展示，是否超标以后端 precheck 为准 */
export function perPersonFen(amountFen: number, headcount: number): number {
  return headcount > 0 ? Math.round(amountFen / headcount) : 0
}

/** 表单上的「共 N 人，人均 ¥xx」；金额还没填时只显示人数 */
export function headcountSummary(amountYuan: string, headcount: number): string {
  const fen = yuanToFen(amountYuan)
  if (fen === null || fen <= 0) return `共 ${headcount} 人`
  return `共 ${headcount} 人，人均 ${formatFen(perPersonFen(fen, headcount))}`
}

/** 勾选 / 取消一个参与人（chip 多选） */
export function toggleId(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
}

/** 参与人相关字段（headcount 仍按同一算法传给后端，兼容旧后端）；只有客户招待需要参与人 */
function participantFields(
  v: ExpenseFormValues,
): Pick<ExpenseCreate, "headcount" | "contact_ids" | "colleague_ids" | "extra_guests"> {
  if (v.type !== "entertainment") return { headcount: 1, contact_ids: [], colleague_ids: [], extra_guests: 0 }
  return {
    headcount: participantCount(v),
    contact_ids: v.contact_ids,
    colleague_ids: v.colleague_ids,
    extra_guests: parseExtraGuests(v.extra_guests) ?? 0,
  }
}

/** 表单 → ExpenseCreate（金额转分；可选字段空不传）。客户招待：必须关联客户，且至少 1 名客户方参与人 */
export function toExpenseCreate(v: ExpenseFormValues, idempotencyKey?: string): FormResult<ExpenseCreate> {
  const errors: ExpenseFormErrors = {}
  const amount = yuanToFen(v.amount)
  if (amount === null || amount <= 0) errors.amount = "请输入大于 0 的金额，最多两位小数"
  if (parseExtraGuests(v.extra_guests) === null) errors.extra_guests = "其他人数为 0–999 的整数"
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.occurred_on)) errors.occurred_on = "请选择发生日期"
  if (!v.reason.trim()) errors.reason = "请填写事由"
  if (v.type === "entertainment") {
    if (!v.customer_id) errors.customer_id = "客户招待需关联客户"
    else if (v.contact_ids.length === 0) errors.contact_ids = "客户招待至少选择 1 名客户方参与人"
  }
  Object.assign(errors, tripErrors(v.type, v.trip))
  if (amount === null || amount <= 0 || Object.keys(errors).length > 0) return { ok: false, errors }
  const body: ExpenseCreate = {
    type: v.type,
    amount,
    occurred_on: v.occurred_on,
    reason: v.reason.trim(),
    ...participantFields(v),
  }
  const details = toDetails(v.type, v.trip)
  if (details) body.details = details
  if (v.customer_id) body.customer_id = v.customer_id
  if (v.customer_id && v.opportunity_id) body.opportunity_id = v.opportunity_id
  if (idempotencyKey) body.idempotency_key = idempotencyKey
  return { ok: true, value: body }
}

/** 已保存的报销单 → 表单（修改草稿、驳回后修改用） */
export function formFromExpense(e: ExpenseDetail): ExpenseFormValues {
  const d = e.details ?? {}
  return {
    type: e.type,
    amount: fenToYuanInput(e.amount),
    occurred_on: e.occurred_on,
    customer_id: e.customer?.id ?? null,
    opportunity_id: e.opportunity?.id ?? null,
    contact_ids: (e.contacts ?? []).map((c) => c.id),
    colleague_ids: (e.colleagues ?? []).map((u) => u.id),
    extra_guests: e.extra_guests ? String(e.extra_guests) : "",
    reason: e.reason ?? "",
    trip: {
      from_city: d.from_city ?? "",
      to_city: d.to_city ?? "",
      transport_mode: d.transport_mode ?? "",
      city: d.city ?? "",
      check_in: d.check_in ?? "",
      check_out: d.check_out ?? "",
    },
  }
}

/** 最近一次审批是驳回时返回它（看驳回原因） */
export function lastRejection(approvals: ApprovalBrief[] | undefined): ApprovalBrief | null {
  const last = approvals?.at(-1)
  return last?.status === "rejected" ? last : null
}

/** 实时制度校验的请求体：只要金额合法就可以校验（事由等可以还没填）；人数随参与人实时变化 */
export function toPrecheckBody(v: ExpenseFormValues): ExpenseCreate | null {
  const amount = yuanToFen(v.amount)
  if (amount === null || amount <= 0 || parseExtraGuests(v.extra_guests) === null) return null
  const body: ExpenseCreate = {
    type: v.type,
    amount,
    occurred_on: v.occurred_on || localDate(),
    reason: v.reason.trim() || "precheck",
    ...participantFields(v),
  }
  if (v.customer_id) body.customer_id = v.customer_id
  // 住宿日期不全时也照样校验：后端会说明「缺少城市或入住 / 离店日期」
  const details = toDetails(v.type, v.trip)
  if (details) body.details = details
  return body
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
  return `${Number((bytes / 1024 / 1024).toFixed(1))} MB` // 10 MB 而不是 10.0 MB
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
  /** person：人均；night：每晚（差旅住宿） */
  unit: PolicyUnit
}

const ruleNote = (ref: string | undefined): string | undefined => (ref ? `依据 ${ref}` : undefined)

export function checkFromPrecheck(p: ExpensePrecheck): PolicyCheckView {
  return {
    over: p.need_approval,
    per_person: p.per_person,
    limit_per_person: p.limit_per_person,
    over_amount: p.over_amount,
    summary: p.reason || undefined,
    note: ruleNote(p.rule_ref),
    unit: p.unit ?? "person",
  }
}

export function checkFromPolicy(p: PolicyCheck): PolicyCheckView {
  return {
    over: !p.passed,
    per_person: p.per_person,
    limit_per_person: p.limit_per_person,
    over_amount: p.over_amount,
    note: ruleNote(p.rule_ref),
    unit: p.unit ?? "person",
  }
}
