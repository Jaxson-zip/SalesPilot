/**
 * 方案卡上调整物料（改数量 / 删行）的预览计算，与 core 的 packs/base.adjust_tier 同一口径：
 * 单价和整单折扣不变，总价 = 目录价合计 × (1 − 折扣)，毛利 = (总价 − 成本) / 总价。
 * 这里只用于即时预览；确认后由后端按目录和规则重新计算，以后端为准。
 */
import type { CoreSolutionTier } from "@/lib/artifacts"

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
  const price = Math.round(listed * (1 - (tier.discount_rate ?? 0)))
  const margin = price > 0 ? Math.round(((price - cost) / price) * 10000) / 10000 : 0
  // 物料变了，按原物料算的成本构成不再准确（后端同样去掉）
  const changed = Object.keys(changedQty(tier, edits)).length > 0
  const specs = changed
    ? Object.fromEntries(Object.entries(tier.specs ?? {}).filter(([k]) => !STALE_SPECS.includes(k)))
    : tier.specs
  return { ...tier, items, specs, total_cost: cost, total_price: price, margin_rate: margin }
}
