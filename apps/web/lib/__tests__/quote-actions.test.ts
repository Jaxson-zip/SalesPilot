import { describe, expect, it } from "vitest"

import { availableQuoteActions, primaryQuoteAction, quoteToBom, submitResultText } from "@/lib/quote-actions"
import type { QuoteAction, QuoteStatus } from "@/types/api"

describe("availableQuoteActions（契约 §3 状态流转）", () => {
  const cases: [QuoteStatus, QuoteAction[]][] = [
    ["draft", ["submit"]],
    ["pending_approval", []],
    ["approved", ["send"]],
    ["sent", ["reject", "accept"]],
    ["accepted", []],
    ["rejected", []],
  ]
  it.each(cases)("%s → %j", (status, actions) => {
    expect(availableQuoteActions(status)).toEqual(actions)
  })

  it("主按钮取最后一个可用操作", () => {
    expect(primaryQuoteAction("sent")).toBe("accept")
    expect(primaryQuoteAction("draft")).toBe("submit")
    expect(primaryQuoteAction("accepted")).toBeNull()
  })
})

describe("submitResultText", () => {
  it("按提交后的状态给出提示", () => {
    expect(submitResultText("approved")).toContain("自动通过")
    expect(submitResultText("pending_approval")).toContain("主管审批")
  })
})

describe("quoteToBom", () => {
  it("明细转物料清单，金额保持分", () => {
    const bom = quoteToBom({
      tier_name: "标准版",
      total_cost: 26250000,
      total_price: 37200000,
      margin_rate: 0.2944,
      estimated_commission: 1488000,
      items: [
        {
          sku: "GPU-1",
          name: "GPU 服务器",
          unit: "台",
          qty: 2,
          unit_cost: 100,
          unit_price: 150,
          category: "hardware",
          subtotal_cost: 200,
          subtotal_price: 300,
        },
      ],
    })
    expect(bom.title).toBe("标准版 · 物料清单")
    expect(bom.items[0]).toEqual({ name: "GPU 服务器", quantity: "2 台", cost: 200, price: 300 })
    expect(bom.totals.map((t) => t.value)).toEqual(["¥262,500", "¥372,000", "29.4%", "¥14,880"])
  })
})
