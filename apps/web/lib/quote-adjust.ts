/**
 * 报价单调价（契约 v3 §14）的纯函数：数量 / 整单折扣的输入解析与实时预览。
 * 预览只用于输入时的即时反馈；保存后总价、毛利、是否需要审批一律以后端（规则代码）返回为准。
 */
import { parsePositiveInt } from "@/lib/money"
import type { QuoteItemsPatch, QuoteLine } from "@/types/api"

/** 每个 sku 的数量（输入框字符串） */
export type QtyDraft = Record<string, string>

export function initialQtyDraft(items: Pick<QuoteLine, "sku" | "qty">[]): QtyDraft {
  return Object.fromEntries(items.map((it) => [it.sku, String(it.qty)]))
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

export function previewAdjust(
  items: Pick<QuoteLine, "sku" | "qty" | "unit_price">[],
  qtys: QtyDraft,
  discountInput: string,
): AdjustPreview {
  let valid = true
  const lines = items.map((it) => {
    const parsed = parsePositiveInt(qtys[it.sku] ?? String(it.qty), { min: 1, max: 100000 })
    if (parsed === null) valid = false
    const qty = parsed ?? it.qty
    return { sku: it.sku, qty, subtotal: it.unit_price * qty }
  })
  const rate = parseDiscountPercent(discountInput)
  if (rate === null) valid = false
  const listTotal = lines.reduce((s, l) => s + l.subtotal, 0)
  const discountAmount = Math.round(listTotal * (rate ?? 0))
  return { valid, lines, listTotal, discountAmount, total: listTotal - discountAmount }
}

/** 与原报价相比是否有改动（有改动才显示「保存调整」） */
export function isAdjustDirty(
  items: Pick<QuoteLine, "sku" | "qty">[],
  qtys: QtyDraft,
  discountInput: string,
  originalRate: number | undefined,
): boolean {
  const qtyChanged = items.some((it) => (qtys[it.sku] ?? String(it.qty)).trim() !== String(it.qty))
  const rate = parseDiscountPercent(discountInput)
  return qtyChanged || rate === null || Math.abs(rate - (originalRate ?? 0)) > 1e-9
}

/** 预览 → PATCH /api/quotes/{id}/items 的请求体；输入非法返回 null */
export function toItemsPatch(
  items: Pick<QuoteLine, "sku" | "qty" | "unit_price">[],
  qtys: QtyDraft,
  discountInput: string,
): QuoteItemsPatch | null {
  const p = previewAdjust(items, qtys, discountInput)
  const rate = parseDiscountPercent(discountInput)
  if (!p.valid || rate === null) return null
  return { items: p.lines.map((l) => ({ sku: l.sku, qty: l.qty })), discount_rate: rate }
}
