/** 新建客户表单 → CustomerCreate（字段对照 core schemas/customer.py；年度预算元 → 分） */
import { yuanToFen } from "@/lib/money"
import type { CustomerCreate, CustomerLevel } from "@/types/api"

/** 行业字典（U7：统一写法，筛选和统计才不会乱） */
export const INDUSTRY_OPTIONS = [
  "法律服务",
  "制造业",
  "医疗",
  "教育",
  "物流",
  "设计",
  "互联网",
  "金融",
  "政府",
  "其他",
] as const

/** 规模区间（人） */
/** 退回公海的常见原因（B5），点选后可补充 */
export const POOL_RELEASE_REASONS = [
  "长期联系不上",
  "预算冻结，暂无采购计划",
  "非目标客户",
  "负责人离职 / 调岗",
] as const

export const SIZE_OPTIONS = ["1–49 人", "50–199 人", "200–499 人", "500–999 人", "1000 人以上"] as const

export interface CustomerFormValues {
  name: string
  industry: string
  level: CustomerLevel
  size: string
  address: string
  website: string
  /** 元 */
  annual_budget: string
}

export type CustomerFormErrors = Partial<Record<keyof CustomerFormValues, string>>

export const EMPTY_CUSTOMER_FORM: CustomerFormValues = {
  name: "",
  industry: "",
  level: "C",
  size: "",
  address: "",
  website: "",
  annual_budget: "",
}

/** 与后端 Field(max_length=...) 一致 */
const MAX_LEN: Partial<Record<keyof CustomerFormValues, number>> = {
  name: 200,
  industry: 50,
  size: 50,
  address: 200,
  website: 200,
}

export function toCustomerCreate(
  v: CustomerFormValues,
): { ok: true; value: CustomerCreate } | { ok: false; errors: CustomerFormErrors } {
  const errors: CustomerFormErrors = {}
  const t = (k: keyof CustomerFormValues) => String(v[k]).trim()
  if (!t("name")) errors.name = "请填写客户名称"
  for (const [k, max] of Object.entries(MAX_LEN) as [keyof CustomerFormValues, number][]) {
    if (!errors[k] && t(k).length > max) errors[k] = `不能超过 ${max} 个字`
  }
  let budget: number | undefined
  if (t("annual_budget")) {
    const fen = yuanToFen(t("annual_budget"))
    if (fen === null) errors.annual_budget = "请输入金额，最多两位小数"
    else budget = fen
  }
  if (Object.keys(errors).length > 0) return { ok: false, errors }
  const value: CustomerCreate = { name: t("name"), level: v.level }
  if (t("industry")) value.industry = t("industry")
  if (t("size")) value.size = t("size")
  if (t("address")) value.address = t("address")
  if (t("website")) value.website = t("website")
  if (budget !== undefined) value.annual_budget = budget
  return { ok: true, value }
}
