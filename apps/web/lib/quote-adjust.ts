/**
 * 报价单调价（契约 v3 §14）的纯函数：数量 / 整单折扣 / 自己加的费用的输入解析与实时预览。
 * 预览只用于输入时的即时反馈；保存后总价、毛利、是否需要审批一律以后端（规则代码）返回为准。
 */
import { fenToYuanInput, parsePositiveInt, yuanToFen } from "@/lib/money"
import type { PackCatalogItem } from "@/lib/pack-rules"
import type { QuoteItemsPatch, QuoteLine } from "@/types/api"

/** 自己加的费用（加急费、差旅、第三方服务等目录里没有的）用这个前缀的 sku */
export const EXTRA_PREFIX = "extra-"

export const isExtraSku = (sku: string) => sku.startsWith(EXTRA_PREFIX)

/** 编辑中的一行（输入框都是字符串）。目录物料能改单价和数量；自己加的费用名称、单价、成本都能改 */
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
  /** 目录物料加进来时的单价（分）：改过单价时显示「原价」 */
  basePrice: number | null
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
    basePrice: isExtraSku(it.sku) ? null : it.unit_price,
  }))
}

/** 从产品目录加一行（目录价、目录成本） */
export function catalogRow(item: Pick<PackCatalogItem, "sku" | "name" | "unit" | "cost" | "price">): DraftRow {
  return {
    sku: item.sku,
    name: item.name,
    unit: item.unit,
    qty: "1",
    price: fenToYuanInput(item.price),
    cost: item.cost ? fenToYuanInput(item.cost) : "",
    extra: false,
    basePrice: item.price,
  }
}

let seq = 0
/** 新加一行费用：sku 只需在这张报价单里不重复 */
export function newExtraRow(): DraftRow {
  seq += 1
  const sku = `${EXTRA_PREFIX}${Date.now().toString(36)}${seq}`
  return { sku, name: "", unit: "项", qty: "1", price: "", cost: "", extra: true, basePrice: null }
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
  /** 预估毛利率（合计为 0 时为 null）；保存后以后端为准 */
  margin: number | null
}

export function previewAdjust(rows: DraftRow[], discountInput: string): AdjustPreview {
  const parsed = rows.map(parseRow)
  const rate = parseDiscountPercent(discountInput)
  const valid = rows.length > 0 && rate !== null && parsed.every((p) => p.valid)
  const lines = parsed.map((p) => ({ sku: p.sku, qty: p.qty, subtotal: p.unitPrice * p.qty }))
  const listTotal = lines.reduce((s, l) => s + l.subtotal, 0)
  const discountAmount = Math.round(listTotal * (rate ?? 0))
  const total = listTotal - discountAmount
  const cost = parsed.reduce((s, p) => s + p.unitCost * p.qty, 0)
  const margin = total > 0 ? (total - cost) / total : null
  return { valid, lines, listTotal, discountAmount, total, margin }
}

export interface ApprovalRules {
  /** 毛利底线（低于要主管审批） */
  floor: number
  /** 销售折扣权限（比目录价低得超过这个比例要主管审批） */
  maxDiscount: number
}

/** 行业包详情里的规则（GET /api/packs/{id} 的 rules，已合并网页上的修改）→ 审批阈值；缺了返回 null */
export function approvalRules(rules: Record<string, unknown> | undefined): ApprovalRules | null {
  const get = (sec: string, key: string) => {
    const s = rules?.[sec]
    const v = typeof s === "object" && s !== null ? (s as Record<string, unknown>)[key] : null
    return typeof v === "number" && Number.isFinite(v) ? v : null
  }
  const floor = get("margin", "floor_rate")
  const maxDiscount = get("discount", "max_rate")
  return floor === null || maxDiscount === null ? null : { floor, maxDiscount }
}

/**
 * 提交后会不会进主管审批（和 core quote_service.approval_reasons 一致）：
 * 毛利低于底线；或比目录价低得超过折扣权限（目录物料按目录价比，压单价和填折扣一样算折扣）。
 * 返回原因，空数组表示会自动通过；输入不合法返回 null。
 */
export function approvalPreview(
  rows: DraftRow[],
  discountInput: string,
  catalogPrices: Record<string, number>,
  rules: ApprovalRules,
): string[] | null {
  const p = previewAdjust(rows, discountInput)
  if (!p.valid) return null
  const reasons: string[] = []
  const cost = rows.map(parseRow).reduce((s, r) => s + r.unitCost * r.qty, 0)
  // 后端毛利率保留 4 位小数后再和底线比
  const margin = p.total > 0 ? Math.round(((p.total - cost) / p.total) * 10000) / 10000 : 0
  if (!(p.total > 0 && margin >= rules.floor)) {
    reasons.push(`毛利 ${(margin * 100).toFixed(1)}% 低于底线 ${Math.round(rules.floor * 100)}%`)
  }
  const base = p.lines.reduce((s, l) => s + (catalogPrices[l.sku] ?? l.subtotal / l.qty) * l.qty, 0)
  const off = base > 0 ? (base - p.total) / base : 0
  if (off > rules.maxDiscount + 1e-9) {
    reasons.push(`比目录价低 ${(off * 100).toFixed(1)}%，超出销售折扣权限 ${Math.round(rules.maxDiscount * 100)}%`)
  }
  return reasons
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
    if (!r.extra) return { sku: r.sku, qty: p.qty, unit_price: p.unitPrice }
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
