/**
 * 报价单调价（契约 v3 §14）的纯函数：数量 / 整单折扣 / 自己加的费用的输入解析与实时预览。
 * 预览只用于输入时的即时反馈；保存后总价、毛利、是否需要审批一律以后端（规则代码）返回为准。
 */
import { fenToYuanInput, parsePositiveInt, yuanToFen } from "@/lib/money"
import type { QuoteItemsPatch, QuoteLine } from "@/types/api"

/** 自己加的费用（加急费、差旅、第三方服务等目录里没有的）用这个前缀的 sku */
export const EXTRA_PREFIX = "extra-"

export const isExtraSku = (sku: string) => sku.startsWith(EXTRA_PREFIX)

/** 编辑中的一行（输入框都是字符串）。目录物料只能改数量；自己加的费用名称、单价、成本都能改 */
export interface DraftRow {
  sku: string
  name: string
  unit: string
  qty: string
  /** 单价（元） */
  price: string
  /** 成本（元，可不填，按 0 算） */
  cost: string
  extra: boolean
}

type SourceLine = Pick<QuoteLine, "sku" | "name" | "unit" | "qty" | "unit_price" | "unit_cost">

export function initialDraft(items: SourceLine[]): DraftRow[] {
  return items.map((it) => ({
    sku: it.sku,
    name: it.name,
    unit: it.unit,
    qty: String(it.qty),
    price: fenToYuanInput(it.unit_price),
    cost: it.unit_cost ? fenToYuanInput(it.unit_cost) : "",
    extra: isExtraSku(it.sku),
  }))
}

let seq = 0
/** 新加一行费用：sku 只需在这张报价单里不重复 */
export function newExtraRow(): DraftRow {
  seq += 1
  const sku = `${EXTRA_PREFIX}${Date.now().toString(36)}${seq}`
  return { sku, name: "", unit: "项", qty: "1", price: "", cost: "", extra: true }
}

/** 折扣输入（百分比，例如 "8" 表示 8%）→ 0–1 的比例；空 = 0；必须 0 ≤ x < 100，最多 1 位小数 */
export function parseDiscountPercent(input: string): number | null {
  const s = input.trim().replace(/%$/, "")
  if (!s) return 0
  if (!/^\d{1,2}(\.\d)?$/.test(s)) return null
  const pct = Number(s)
  return pct >= 0 && pct < 100 ? Math.round(pct * 10) / 1000 : null
}

/** 0.08 → "8"；0.125 → "12.5" */
export function discountToInput(rate: number | undefined): string {
  if (!rate) return ""
  return String(Math.round(rate * 1000) / 10)
}

interface ParsedRow {
  sku: string
  qty: number
  unitPrice: number
  unitCost: number
  valid: boolean
}

function parseRow(r: DraftRow): ParsedRow {
  const qty = parsePositiveInt(r.qty, { min: 1, max: 100000 })
  const price = yuanToFen(r.price)
  const cost = r.cost.trim() ? yuanToFen(r.cost) : 0
  const valid = qty !== null && price !== null && cost !== null && (!r.extra || r.name.trim() !== "")
  return { sku: r.sku, qty: qty ?? 0, unitPrice: price ?? 0, unitCost: cost ?? 0, valid }
}

export interface AdjustPreview {
  /** 有非法输入时为 false（不能保存） */
  valid: boolean
  lines: { sku: string; qty: number; subtotal: number }[]
  /** 折前合计（分） */
  listTotal: number
  /** 折扣金额（分，四舍五入） */
  discountAmount: number
  /** 预览合计（分） */
  total: number
}

export function previewAdjust(rows: DraftRow[], discountInput: string): AdjustPreview {
  const parsed = rows.map(parseRow)
  const rate = parseDiscountPercent(discountInput)
  const valid = rows.length > 0 && rate !== null && parsed.every((p) => p.valid)
  const lines = parsed.map((p) => ({ sku: p.sku, qty: p.qty, subtotal: p.unitPrice * p.qty }))
  const listTotal = lines.reduce((s, l) => s + l.subtotal, 0)
  const discountAmount = Math.round(listTotal * (rate ?? 0))
  return { valid, lines, listTotal, discountAmount, total: listTotal - discountAmount }
}

const sameRow = (a: DraftRow, b: DraftRow) =>
  a.sku === b.sku &&
  a.qty.trim() === b.qty.trim() &&
  a.name.trim() === b.name.trim() &&
  a.price.trim() === b.price.trim() &&
  a.cost.trim() === b.cost.trim()

/** 与原报价相比是否有改动（有改动才显示「保存调整」） */
export function isAdjustDirty(
  items: SourceLine[],
  rows: DraftRow[],
  discountInput: string,
  originalRate: number | undefined,
): boolean {
  const before = initialDraft(items)
  const rowsChanged = before.length !== rows.length || before.some((b, i) => !sameRow(b, rows[i]))
  const rate = parseDiscountPercent(discountInput)
  return rowsChanged || rate === null || Math.abs(rate - (originalRate ?? 0)) > 1e-9
}

/** 草稿 → PATCH /api/quotes/{id}/items 的请求体；输入非法返回 null */
export function toItemsPatch(rows: DraftRow[], discountInput: string): QuoteItemsPatch | null {
  const rate = parseDiscountPercent(discountInput)
  if (rate === null || !previewAdjust(rows, discountInput).valid) return null
  const items = rows.map((r) => {
    const p = parseRow(r)
    if (!r.extra) return { sku: r.sku, qty: p.qty }
    return {
      sku: r.sku,
      qty: p.qty,
      name: r.name.trim(),
      unit: r.unit.trim() || "项",
      unit_price: p.unitPrice,
      unit_cost: p.unitCost,
    }
  })
  return { items, discount_rate: rate }
}
