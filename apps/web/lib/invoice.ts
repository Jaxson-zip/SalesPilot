/** 开票跟踪（回款计划每一期）的纯函数：状态文案、可做的操作 */
import type { InvoiceEvent, InvoiceStatus, InvoiceType, PaymentPlanItem } from "@/types/api"

export const INVOICE_STATUS_META: Record<InvoiceStatus, { label: string; color: "gray" | "orange" | "green" }> = {
  none: { label: "未开票", color: "gray" },
  requested: { label: "已申请", color: "orange" },
  issued: { label: "已开票", color: "green" },
}

export const INVOICE_TYPE_OPTIONS: { value: InvoiceType; label: string }[] = [
  { value: "special", label: "增值税专用发票" },
  { value: "normal", label: "增值税普通发票" },
]

export const invoiceTypeName = (t?: InvoiceType | null) => (t === "normal" ? "普票" : t === "special" ? "专票" : "")

export type InvoiceAction = "request" | "issue" | "void"

/** 这一期当前能做的开票操作：负责人申请；主管登记（可不经申请）或作废 */
export function invoiceActions(item: PaymentPlanItem, who: { owner: boolean; manager: boolean }): InvoiceAction[] {
  const status = item.invoice_status ?? "none"
  const out: InvoiceAction[] = []
  if (who.owner && status === "none") out.push("request")
  if (who.manager && status !== "issued") out.push("issue")
  if (who.manager && status !== "none") out.push("void")
  return out
}

/** 发票列的说明：已开票显示类型和号码，已申请显示类型；已开票未收齐提示天数 */
export function invoiceDetail(item: PaymentPlanItem): string {
  const type = invoiceTypeName(item.invoice_type)
  if (item.invoice_status === "issued") {
    const unpaid = item.invoiced_unpaid_days ? ` · 开票 ${item.invoiced_unpaid_days} 天未收齐` : ""
    return `${type} ${item.invoice_no ?? ""}`.trim() + unpaid
  }
  if (item.invoice_status === "requested") return [type, item.invoice_note].filter(Boolean).join(" · ")
  return ""
}

/**
 * 开票历史一条的说明。作废记录带原票（号码、开票日）和原因：作废会清空这一期上的发票字段，
 * 重新开票后只能在这里查到原来那张。
 */
export function invoiceEventText(e: InvoiceEvent): string {
  const type = invoiceTypeName(e.invoice_type)
  if (e.action === "request") return ["申请开票", type, e.note].filter(Boolean).join(" · ")
  if (e.action === "issue") return `登记开票 · ${type} ${e.invoice_no ?? ""}`.trim()
  const what =
    e.from_status === "issued"
      ? `作废发票 · ${type} ${e.invoice_no ?? ""}`.trim() + (e.invoiced_on ? `（开票日 ${e.invoiced_on}）` : "")
      : "撤回开票申请"
  return e.note ? `${what} · 原因：${e.note}` : what
}
