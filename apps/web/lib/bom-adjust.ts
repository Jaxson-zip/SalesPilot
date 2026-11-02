/**
 * 方案卡上调整物料（改数量 / 删行）的预览计算，与 core 的 packs/base.adjust_tier 同一口径：
 * 单价和整单折扣不变，总价 = 目录价合计 × (1 − 折扣)，毛利 = (总价 − 成本) / 总价。
 * 这里只用于即时预览；确认后由后端按目录和规则重新计算，以后端为准。
 */
import type { CoreSolutionTier } from "@/lib/artifacts"
import { discountedPrice } from "@/lib/money"

/** sku → 新数量（0 表示删除）；只记录改过的 */
export type QtyEdits = Record<string, number>

export const MAX_ADJUST_QTY = 9999
const STALE_SPECS = ["cost_breakdown", "ai_monthly_cost"]

/** 输入框文字 → 数量；不是 0～9999 的整数返回 undefined */
export function parseQty(text: string): number | undefined {
  if (!/^\d{1,4}$/.test(text.trim())) return undefined
  return Number(text.trim())
}

/** 去掉和原方案一样的数量，只留真正改过的 */
export function changedQty(tier: CoreSolutionTier, edits: QtyEdits): QtyEdits {
  const out: QtyEdits = {}
  for (const i of tier.items) {
    const q = edits[i.sku]
    if (q !== undefined && q !== i.qty) out[i.sku] = q
  }
  return out
}

export function adjustTier(tier: CoreSolutionTier, edits: QtyEdits): CoreSolutionTier {
  const items = tier.items.map((i) => ({ ...i, qty: edits[i.sku] ?? i.qty })).filter((i) => i.qty > 0)
  const cost = items.reduce((s, i) => s + i.unit_cost * i.qty, 0)
  const listed = items.reduce((s, i) => s + i.unit_price * i.qty, 0)
  const price = discountedPrice(listed, tier.discount_rate ?? 0)
  const margin = price > 0 ? Math.round(((price - cost) / price) * 10000) / 10000 : 0
  // 物料变了，按原物料算的成本构成不再准确（后端同样去掉）
  const changed = Object.keys(changedQty(tier, edits)).length > 0
  const specs = changed
    ? Object.fromEntries(Object.entries(tier.specs ?? {}).filter(([k]) => !STALE_SPECS.includes(k)))
    : tier.specs
  const summary = changed ? adjustedSummary(tier, edits) : tier.summary
  return { ...tier, items, specs, summary, total_cost: cost, total_price: price, margin_rate: margin }
}

const personDays = (items: { unit: string; qty: number }[]): number =>
  items.filter((i) => i.unit === "人天").reduce((s, i) => s + i.qty, 0)

/**
 * 调整后的方案摘要：原摘要按原物料写（模块数、人天），调整后不再准确，改为按当前物料汇总。
 * 与 core 的 packs/base.adjusted_summary 同一口径。
 */
export function adjustedSummary(tier: CoreSolutionTier, edits: QtyEdits): string {
  const after = tier.items.map((i) => ({ ...i, qty: edits[i.sku] ?? i.qty }))
  const removed = after.filter((i) => i.qty === 0).map((i) => i.name)
  const changed = Object.keys(changedQty(tier, edits)).length - removed.length
  const parts: string[] = []
  const before = personDays(tier.items)
  if (before > 0) parts.push(`人天合计 ${personDays(after)} 人天（原方案约 ${before} 人天）`)
  if (removed.length) parts.push(`去掉 ${removed.join("、")}`)
  if (changed > 0) parts.push(`改了 ${changed} 项数量`)
  return `已调整：${parts.join("；")}`
}
