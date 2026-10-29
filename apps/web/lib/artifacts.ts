import { formatFen, formatPercent } from "@/lib/format"
import { fenToYuan, toCsv } from "@/lib/list-view"
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
  /** 行业包附加信息；软件外包带 cost_breakdown（分）和 ai_monthly_cost（分/月） */
  specs?: Record<string, unknown>
}

/** 成本构成（软件外包）：人工 / AI 编码工具 / 第三方代采 / 部署运维等服务，单位分 */
const COST_LABELS: [string, string][] = [
  ["labor", "其中人工"],
  ["ai_tools", "其中 AI 编码工具"],
  ["third_party", "其中第三方代采"],
  ["services", "其中部署运维"],
]

function costTotals(specs: Record<string, unknown> | undefined): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = []
  const cb = specs?.cost_breakdown
  if (isObj(cb))
    for (const [k, label] of COST_LABELS) if (typeof cb[k] === "number") out.push({ label, value: formatFen(cb[k]) })
  const ai = specs?.ai_monthly_cost
  if (typeof ai === "number" && ai > 0) out.push({ label: "上线后 AI 调用费（客户付）", value: `${formatFen(ai)}/月` })
  return out
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
    key: t.tier,
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
      ...costTotals(t.specs),
    ],
  }
}

/** 物料清单 → CSV（金额按元，两位小数）；合计行附在末尾 */
export function bomToCsv(bom: BomData): string {
  const rows: { name: string; quantity: string; cost: string; price: string }[] = bom.items.map((r) => ({
    name: r.name,
    quantity: r.quantity,
    cost: fenToYuan(r.cost),
    price: fenToYuan(r.price),
  }))
  for (const t of bom.totals) rows.push({ name: t.label, quantity: "", cost: "", price: t.value })
  return toCsv(
    [
      { label: "项目", value: (r) => r.name },
      { label: "数量", value: (r) => r.quantity },
      { label: "成本（元）", value: (r) => r.cost },
      { label: "售价（元）", value: (r) => r.price },
    ],
    rows,
  )
}

/** 导出文件名：去掉文件名里不允许的字符 */
export function safeFileName(title: string): string {
  return title.replace(/[\/:*?"<>|\s·]+/g, "-").replace(/^-+|-+$/g, "") || "物料清单"
}
