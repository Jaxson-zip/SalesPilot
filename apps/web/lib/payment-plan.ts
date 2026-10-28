/** 回款计划编辑（B9）的纯函数：表单行 ↔ 接口数据、提交前校验（最终以 core 的 42201 为准） */
import { formatFen } from "@/lib/format"
import { fenToYuanInput, yuanToFen } from "@/lib/money"
import type { PaymentPlanItem, PaymentPlanUpdate } from "@/types/api"

export interface PlanRow {
  name: string
  /** 元，字符串（MoneyInput） */
  amount: string
  /** YYYY-MM-DD */
  due_date: string
}

export function toRows(items: PaymentPlanItem[]): PlanRow[] {
  return items.map((i) => ({ name: i.name, amount: fenToYuanInput(i.amount), due_date: i.due_date }))
}

/** 已填金额合计（分）；填错的行按 0 计 */
export function rowsTotal(rows: PlanRow[]): number {
  return rows.reduce((sum, r) => sum + (yuanToFen(r.amount) ?? 0), 0)
}

export type PlanCheck = { ok: true; value: PaymentPlanUpdate } | { ok: false; error: string }

export function checkPlan(rows: PlanRow[], contractAmount: number): PlanCheck {
  if (rows.length === 0) return { ok: false, error: "至少需要一期" }
  const items: PaymentPlanUpdate["items"] = []
  for (const [i, r] of rows.entries()) {
    const label = `第 ${i + 1} 期`
    if (!r.name.trim()) return { ok: false, error: `${label}没有填写名称` }
    const amount = yuanToFen(r.amount)
    if (amount === null || amount <= 0) return { ok: false, error: `${label}金额要大于 0，最多两位小数` }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(r.due_date)) return { ok: false, error: `${label}没有填写到期日` }
    items.push({ name: r.name.trim(), amount, due_date: r.due_date })
  }
  const diff = contractAmount - items.reduce((s, x) => s + x.amount, 0)
  if (diff !== 0) {
    const how = diff > 0 ? `还差 ${formatFen(diff)}` : `多了 ${formatFen(-diff)}`
    return { ok: false, error: `各期合计要等于合同金额 ${formatFen(contractAmount)}，${how}` }
  }
  return { ok: true, value: { items } }
}
