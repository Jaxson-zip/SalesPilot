import { formatFen, formatPercent } from "@/lib/format"
import type { BomData, SolutionTier } from "@/types/api"

/**
 * core 推送的 artifact 原始结构（与 services/core/app/packs/base.py 的 SolutionTier / BomItem 一致）。
 * 前端组件使用更贴近展示的视图模型，这里负责转换。金额单位均为「分」，毛利率为 0–1。
 */
export interface CoreBomItem {
  sku: string
  name: string
  category: string
  unit: string
  qty: number
  unit_cost: number
  unit_price: number
}

export interface CoreSolutionTier {
  tier: string
  name: string
  summary: string
  items: CoreBomItem[]
  total_cost: number
  total_price: number
  margin_rate: number
  recommended?: boolean
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null

export function isCoreTier(v: unknown): v is CoreSolutionTier {
  return (
    isObj(v) &&
    typeof v.name === "string" &&
    typeof v.total_price === "number" &&
    typeof v.margin_rate === "number" &&
    Array.isArray(v.items)
  )
}

export function isCoreTiers(v: unknown): v is CoreSolutionTier[] {
  return Array.isArray(v) && v.length > 0 && v.every(isCoreTier)
}

export function toTierCards(tiers: CoreSolutionTier[]): SolutionTier[] {
  return tiers.map((t) => ({
    name: t.name,
    spec: t.summary,
    price: t.total_price,
    margin: t.margin_rate,
    recommended: t.recommended ?? false,
  }))
}

export function toBomData(t: CoreSolutionTier): BomData {
  return {
    title: `${t.name} · 物料清单`,
    items: t.items.map((i) => ({
      name: i.name,
      quantity: `${i.qty} ${i.unit}`,
      cost: i.unit_cost * i.qty,
      price: i.unit_price * i.qty,
    })),
    totals: [
      { label: "成本合计", value: formatFen(t.total_cost) },
      { label: "报价合计", value: formatFen(t.total_price) },
      { label: "毛利率", value: formatPercent(t.margin_rate) },
    ],
  }
}
