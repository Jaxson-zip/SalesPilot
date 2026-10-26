/** 报价单打印页的纯函数：合计、折扣（均来自后端返回的明细与总价，不重新计算价格规则） */
import type { QuoteDetail } from "@/types/api"

export const PRINT_COMPANY = "SalesPilot 演示公司"

export interface PrintTotals {
  /** 明细小计之和（折前，分） */
  subtotal: number
  /** 折扣金额（分）= 折前 − 报价合计；没有折扣为 0 */
  discountAmount: number
  /** 报价合计（分，后端 total_price） */
  total: number
  /** 0–1；后端没返回时按金额反推 */
  discountRate: number
}

export function printTotals(q: Pick<QuoteDetail, "items" | "total_price" | "discount_rate">): PrintTotals {
  const subtotal = q.items.reduce((s, it) => s + it.subtotal_price, 0)
  const discountAmount = Math.max(0, subtotal - q.total_price)
  const discountRate = q.discount_rate ?? (subtotal > 0 ? discountAmount / subtotal : 0)
  return { subtotal, discountAmount, total: q.total_price, discountRate }
}

/** 打印页标题（浏览器「存为 PDF」默认文件名）：报价单-Q-2026-018-客户名 */
export function printDocTitle(q: Pick<QuoteDetail, "code" | "customer">): string {
  return ["报价单", q.code, q.customer?.name].filter(Boolean).join("-")
}
