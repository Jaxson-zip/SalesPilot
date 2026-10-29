/** 合同要素确认单（合同打印页）的纯函数：标题、回款计划比例与核对 */
import type { ContractItem, PaymentPlanItem } from "@/types/api"

/** 浏览器「存为 PDF」默认文件名：合同要素确认单-C-2026-001-客户名 */
export function contractDocTitle(c: Pick<ContractItem, "code" | "customer">): string {
  return ["合同要素确认单", c.code, c.customer?.name].filter(Boolean).join("-")
}

/** 某期占合同金额的比例，取整到 1%：「30%」 */
export function planRatio(amount: number, total: number): string {
  return total > 0 ? `${Math.round((amount / total) * 100)}%` : "—"
}

/** 回款计划各期之和与合同金额不一致时给出差额（分），一致为 0 */
export function planGap(items: Pick<PaymentPlanItem, "amount">[], total: number): number {
  return total - items.reduce((s, it) => s + it.amount, 0)
}
