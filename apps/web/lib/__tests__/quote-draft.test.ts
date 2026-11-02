import { describe, expect, it } from "vitest"

import type { CoreSolutionTier } from "@/lib/artifacts"
import { quoteDraftKey, restoreDraft, serializeDraft, tiersFingerprint } from "@/lib/quote-draft"

const item = (sku: string, qty: number) => ({
  sku,
  name: sku,
  category: "service",
  unit: "人天",
  qty,
  unit_cost: 800,
  unit_price: 1600,
})
const tiers: CoreSolutionTier[] = [
  {
    tier: "economy",
    name: "经济版",
    summary: "",
    items: [item("A", 10)],
    total_cost: 8000,
    total_price: 16000,
    margin_rate: 0.5,
    recommended: true,
  },
  {
    tier: "standard",
    name: "标准版",
    summary: "",
    items: [item("A", 12), item("B", 3)],
    total_cost: 12000,
    total_price: 24000,
    margin_rate: 0.5,
  },
]
const fp = tiersFingerprint(tiers)

describe("quote-draft", () => {
  // 回归（复测 UX01）：选了标准版、加了 1 人天，换页或刷新回来变回默认经济版，没有任何提示
  it("存下的档位和数量调整能原样恢复", () => {
    const raw = serializeDraft(fp, { picked: "standard", edits: { standard: { A: 13 } } })
    expect(restoreDraft(raw, fp, tiers)).toEqual({
      status: "restored",
      draft: { picked: "standard", edits: { standard: { A: 13 } } },
    })
  })

  it("方案重新生成过（指纹不同）不恢复，提示重新核对", () => {
    const raw = serializeDraft("old", { picked: "standard", edits: {} })
    expect(restoreDraft(raw, fp, tiers).status).toBe("stale")
    expect(restoreDraft("{坏数据", fp, tiers).status).toBe("stale")
  })

  it("没改动不存；不认识的档位、物料和非法数量丢掉", () => {
    expect(serializeDraft(fp, { picked: null, edits: { economy: {} } })).toBeNull()
    expect(restoreDraft(null, fp, tiers).status).toBe("none")
    const raw = JSON.stringify({ fp, picked: "pro", edits: { standard: { A: -1, B: 2, Z: 5 }, pro: { A: 1 } } })
    expect(restoreDraft(raw, fp, tiers)).toEqual({
      status: "restored",
      draft: { picked: null, edits: { standard: { B: 2 } } },
    })
  })

  it("按用户和会话分开存", () => {
    expect(quoteDraftKey("u1", "t1")).not.toBe(quoteDraftKey("u2", "t1"))
  })
})
