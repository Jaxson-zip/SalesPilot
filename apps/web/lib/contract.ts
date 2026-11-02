/** 合同回款的纯函数：进度百分比、登记回款前的前端校验（最终以 core 的 42201 为准） */
import { formatFen } from "@/lib/format"
import { fenToYuanInput, yuanToFen } from "@/lib/money"
import type { ContractItem } from "@/types/api"

/** paid_ratio（0–1）→ 0–100 的整数百分比，越界时夹紧 */
/** 打开某份合同：合同列表页带 plan 参数，直接展开这份合同的回款计划 */
export function contractHref(id: string): string {
  return `/contracts?plan=${encodeURIComponent(id)}`
}

export function paidPercent(ratio: number): number {
  if (!Number.isFinite(ratio)) return 0
  return Math.min(100, Math.max(0, Math.round(ratio * 100)))
}

export function unpaidOf(c: Pick<ContractItem, "amount" | "paid_amount">): number {
  return Math.max(0, c.amount - c.paid_amount)
}

/** 登记回款时预填的金额（元，输入框格式）：下一期还没收的部分，没有回款计划时为全部未回款；已收齐为空 */
export function suggestedPayment(c: Pick<ContractItem, "amount" | "paid_amount" | "next_payment">): string {
  const unpaid = unpaidOf(c)
  const next = c.next_payment ? Math.min(c.next_payment.amount, unpaid) : unpaid
  return next > 0 ? fenToYuanInput(next) : ""
}

export type PaymentCheck = { ok: true; amount: number } | { ok: false; error: string }

export function checkPayment(input: string, c: Pick<ContractItem, "amount" | "paid_amount">): PaymentCheck {
  const amount = yuanToFen(input)
  if (amount === null || amount <= 0) return { ok: false, error: "请输入大于 0 的金额，最多两位小数" }
  const balance = unpaidOf(c)
  if (amount > balance) return { ok: false, error: `超过未回款金额 ${formatFen(balance)}` }
  return { ok: true, amount }
}

/**
 * 一次登记的请求键：打开登记框时生成，重试沿用。第一次已入账但页面没收到响应时，
 * 再点一次不会多记一笔。非 HTTPS 页面没有 randomUUID，退回时间 + 随机数。
 */
export function newRequestKey(): string {
  const uuid = globalThis.crypto?.randomUUID?.()
  return `pay-${uuid ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`}`
}
