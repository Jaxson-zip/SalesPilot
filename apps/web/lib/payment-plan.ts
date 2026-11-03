/** 回款计划编辑（B9）的纯函数：表单行 ↔ 接口数据、提交前校验（最终以 core 的 42201 为准） */
import { formatFen } from "@/lib/format"
import { fenToYuanInput, yuanToFen } from "@/lib/money"
import type { PaymentPlanItem, PaymentPlanUpdate, PaymentPlanView } from "@/types/api"

/** 已经发生业务的期次（与 core payment_plan_change 一致）：
 * paid 已收齐，整行不能改；partial 收了一部分，不能删、金额不能低于已收；invoiced 已申请 / 已开票，不能删、金额不能改 */
export type PlanLock = "paid" | "partial" | "invoiced"

export interface PlanRow {
  name: string
  /** 元，字符串（MoneyInput） */
  amount: string
  /** YYYY-MM-DD */
  due_date: string
  lock?: PlanLock
  /** 已冲抵到这一期的金额（分），有 lock 时才有 */
  paid?: number
}

export function lockOf(i: PaymentPlanItem): PlanLock | undefined {
  if (i.status === "paid") return "paid"
  if (i.paid > 0) return "partial"
  if ((i.invoice_status ?? "none") !== "none") return "invoiced"
  return undefined
}

export function toRows(items: PaymentPlanItem[]): PlanRow[] {
  return items.map((i) => {
    const lock = lockOf(i)
    const row = { name: i.name, amount: fenToYuanInput(i.amount), due_date: i.due_date }
    return lock ? { ...row, lock, paid: i.paid } : row
  })
}

/** 合同已有回款、逾期或开票：调整计划要写原因 */
export function planNeedsReason(plan: PaymentPlanView): boolean {
  return (
    plan.paid_amount > 0 || plan.items.some((i) => i.status === "overdue" || (i.invoice_status ?? "none") !== "none")
  )
}

/** 所有期次都已收齐：没有能调整的地方 */
export function planFullyPaid(plan: PaymentPlanView): boolean {
  return plan.items.every((i) => i.status === "paid")
}

/** 已填金额合计（分）；填错的行按 0 计 */
export function rowsTotal(rows: PlanRow[]): number {
  return rows.reduce((sum, r) => sum + (yuanToFen(r.amount) ?? 0), 0)
}

export type PlanCheck = { ok: true; value: PaymentPlanUpdate } | { ok: false; error: string }

export function checkPlan(rows: PlanRow[], contractAmount: number, reason = "", needReason = false): PlanCheck {
  if (rows.length === 0) return { ok: false, error: "至少需要一期" }
  const items: PaymentPlanUpdate["items"] = []
  for (const [i, r] of rows.entries()) {
    const label = `第 ${i + 1} 期`
    if (!r.name.trim()) return { ok: false, error: `${label}没有填写名称` }
    const amount = yuanToFen(r.amount)
    if (amount === null || amount <= 0) return { ok: false, error: `${label}金额要大于 0，最多两位小数` }
    if (r.lock === "partial" && amount < (r.paid ?? 0))
      return { ok: false, error: `${label}已收 ${formatFen(r.paid ?? 0)}，金额不能低于已收` }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(r.due_date)) return { ok: false, error: `${label}没有填写到期日` }
    items.push({ name: r.name.trim(), amount, due_date: r.due_date })
  }
  const diff = contractAmount - items.reduce((s, x) => s + x.amount, 0)
  if (diff !== 0) {
    const how = diff > 0 ? `还差 ${formatFen(diff)}` : `多了 ${formatFen(-diff)}`
    return { ok: false, error: `各期合计要等于合同金额 ${formatFen(contractAmount)}，${how}` }
  }
  const why = reason.trim()
  if (needReason && !why) return { ok: false, error: "这份合同已有回款、逾期或开票，请写明调整原因" }
  return { ok: true, value: why ? { items, reason: why } : { items } }
}
