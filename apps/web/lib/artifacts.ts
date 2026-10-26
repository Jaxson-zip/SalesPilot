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

/** generate_quote 写入成功后推送的报价单（core QuoteOut 的子集） */
export interface CoreQuote {
  id: string
  code: string
  status: string
  total_price: number
  margin_rate: number
}

export const QUOTE_STATUS: Record<string, { label: string; color: "gray" | "yellow" | "blue" | "green" | "red" }> = {
  draft: { label: "草稿", color: "gray" },
  pending_approval: { label: "待主管审批", color: "yellow" },
  approved: { label: "已审批", color: "blue" },
  sent: { label: "已发送客户", color: "blue" },
  accepted: { label: "已成交", color: "green" },
  rejected: { label: "已驳回", color: "red" },
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null

export function isCoreQuote(v: unknown): v is CoreQuote {
  return isObj(v) && typeof v.id === "string" && typeof v.code === "string" && typeof v.total_price === "number"
}

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
