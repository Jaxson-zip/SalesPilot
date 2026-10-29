import { describe, expect, it } from "vitest"

import type { CoreSolutionTier } from "@/lib/artifacts"
import { adjustTier, changedQty, parseQty } from "@/lib/bom-adjust"

const tier: CoreSolutionTier = {
  tier: "standard",
  name: "标准版",
  summary: "",
  discount_rate: 0.1,
  items: [
    { sku: "A", name: "服务器", category: "hardware", unit: "台", qty: 2, unit_cost: 70, unit_price: 100 },
    { sku: "B", name: "监控", category: "service", unit: "项", qty: 1, unit_cost: 10, unit_price: 40 },
  ],
  total_cost: 150,
  total_price: 216,
  margin_rate: 0.3056,
  specs: { cost_breakdown: { labor: 1 }, gpu: "L20" },
}

describe("adjustTier", () => {
  it("删一项、改数量后按单价和折扣重算（与后端 adjust_tier 同口径）", () => {
    const out = adjustTier(tier, { A: 3, B: 0 })
    expect(out.items.map((i) => [i.sku, i.qty])).toEqual([["A", 3]])
    expect([out.total_cost, out.total_price]).toEqual([210, 270])
    expect(out.margin_rate).toBe(0.2222)
    expect(out.specs).toEqual({ gpu: "L20" })
  })

  it("没改动时原样，成本构成保留", () => {
    expect(adjustTier(tier, { A: 2 }).specs).toEqual(tier.specs)
    expect(changedQty(tier, { A: 2, B: 3 })).toEqual({ B: 3 })
  })
})

describe("parseQty", () => {
  it("只接受 0～9999 的整数", () => {
    expect(parseQty(" 10 ")).toBe(10)
    expect(parseQty("0")).toBe(0)
    for (const bad of ["", "-1", "1.5", "10000", "abc"]) expect(parseQty(bad)).toBeUndefined()
  })
})
