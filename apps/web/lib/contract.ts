/** 合同回款的纯函数：进度百分比、登记回款前的前端校验（最终以 core 的 42201 为准） */
import { formatFen } from "@/lib/format"
import { yuanToFen } from "@/lib/money"
import type { ContractItem } from "@/types/api"

/** paid_ratio（0–1）→ 0–100 的整数百分比，越界时夹紧 */
export function paidPercent(ratio: number): number {
  if (!Number.isFinite(ratio)) return 0
  return Math.min(100, Math.max(0, Math.round(ratio * 100)))
}

export function unpaidOf(c: Pick<ContractItem, "amount" | "paid_amount">): number {
  return Math.max(0, c.amount - c.paid_amount)
}

export type PaymentCheck = { ok: true; amount: number } | { ok: false; error: string }

export function checkPayment(input: string, c: Pick<ContractItem, "amount" | "paid_amount">): PaymentCheck {
  const amount = yuanToFen(input)
  if (amount === null || amount <= 0) return { ok: false, error: "请输入大于 0 的金额，最多两位小数" }
  const balance = unpaidOf(c)
  if (amount > balance) return { ok: false, error: `超过未回款金额 ${formatFen(balance)}` }
  return { ok: true, amount }
}
