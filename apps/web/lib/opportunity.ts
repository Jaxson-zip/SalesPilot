/** 新建商机表单 → OpportunityCreate（契约 §2：amount ≥ 0 分，win_rate 0–100，默认 10 由后端给） */
import { parsePositiveInt, yuanToFen } from "@/lib/money"
import type { OpportunityCreate } from "@/types/api"

export interface OpportunityFormValues {
  customer_id: string | null
  name: string
  /** 元 */
  amount: string
  win_rate: string
  expected_close_date: string
  product_line_id: string | null
}

export type OppFormErrors = Partial<Record<keyof OpportunityFormValues, string>>

export function toOpportunityCreate(
  v: OpportunityFormValues,
): { ok: true; value: OpportunityCreate } | { ok: false; errors: OppFormErrors } {
  const errors: OppFormErrors = {}
  if (!v.customer_id) errors.customer_id = "请选择客户"
  if (!v.name.trim()) errors.name = "请填写商机名称"
  const amount = yuanToFen(v.amount)
  if (amount === null) errors.amount = "请输入金额，最多两位小数"
  let winRate: number | undefined
  if (v.win_rate.trim()) {
    const n = parsePositiveInt(v.win_rate, { min: 0, max: 100 })
    if (n === null) errors.win_rate = "赢率为 0–100 的整数"
    else winRate = n
  }
  if (!v.customer_id || amount === null || Object.keys(errors).length > 0) return { ok: false, errors }
  const value: OpportunityCreate = { customer_id: v.customer_id, name: v.name.trim(), amount }
  if (winRate !== undefined) value.win_rate = winRate
  if (v.expected_close_date) value.expected_close_date = v.expected_close_date
  if (v.product_line_id) value.product_line_id = v.product_line_id
  return { ok: true, value }
}
