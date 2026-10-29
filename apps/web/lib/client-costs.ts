/**
 * 运营期客户自付费用（core packs/base.ClientCost）：云服务器、域名证书、小程序认证、大模型调用费等，
 * 实报实销，不含在报价内。金额单位「分」，按 period（年 / 月）计。
 */
import { formatFen } from "@/lib/format"

export interface ClientCost {
  name: string
  amount: number
  period: "year" | "month"
  note?: string
}

export const CLIENT_COSTS_TITLE = "运营期客户自付费用预估（实报实销）"
export const CLIENT_COSTS_NOTE = "以下费用不含在本报价内，由客户按实际发生支付，金额为预估"

export function costAmount(c: ClientCost): string {
  return `${formatFen(c.amount)}/${c.period === "year" ? "年" : "月"}`
}

/** 一句话合计：约 ¥4,100/年 + ¥450/月 */
export function costSummary(costs: ClientCost[]): string {
  const sum = (p: ClientCost["period"]) => costs.filter((c) => c.period === p).reduce((n, c) => n + c.amount, 0)
  const parts = [sum("year") ? `${formatFen(sum("year"))}/年` : "", sum("month") ? `${formatFen(sum("month"))}/月` : ""]
  return parts.filter(Boolean).join(" + ")
}

export function isClientCosts(v: unknown): v is ClientCost[] {
  return (
    Array.isArray(v) &&
    v.every(
      (c) =>
        typeof c === "object" &&
        c !== null &&
        typeof (c as ClientCost).name === "string" &&
        typeof (c as ClientCost).amount === "number",
    )
  )
}
