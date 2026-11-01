import type { PaymentRecord } from "@/types/api"

/** 回款记录的状态标签：冲正记录（负数）/ 已被冲正 / 正常 */
export function paymentKind(p: PaymentRecord): "reversal" | "reversed" | "normal" {
  if (p.reversal_of || p.amount < 0) return "reversal"
  return p.reversed_by ? "reversed" : "normal"
}

/** 主管可以冲正一笔正常的到账记录；冲正记录、已冲正过的不能再冲正（后端同样校验） */
export function canReversePayment(p: PaymentRecord, manager: boolean): boolean {
  return manager && paymentKind(p) === "normal"
}

/** 冲正原因：去掉首尾空格后 2–200 字 */
export function checkReverseReason(reason: string): string | undefined {
  const r = reason.trim()
  if (r.length < 2) return "请写明冲正原因（至少 2 个字），便于财务对账"
  if (r.length > 200) return "冲正原因最多 200 字"
  return undefined
}

/** 一行说明：日期 · 流水号 · 备注 / 冲正原因，没有的项不显示 */
export function paymentDetail(p: PaymentRecord): string {
  const parts = [p.received_on, p.reference_no ? `流水号 ${p.reference_no}` : null]
  parts.push(paymentKind(p) === "reversal" ? `冲正原因：${p.reason ?? "—"}` : p.note)
  return parts.filter(Boolean).join(" · ")
}
