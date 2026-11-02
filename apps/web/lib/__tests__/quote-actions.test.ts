import { describe, expect, it } from "vitest"

import {
  availableQuoteActions,
  canCopyRevision,
  primaryQuoteAction,
  quoteToBom,
  submitResultText,
} from "@/lib/quote-actions"
import type { QuoteAction, QuoteStatus } from "@/types/api"

describe("availableQuoteActions（契约 §3 状态流转）", () => {
  const cases: [QuoteStatus, QuoteAction[]][] = [
    ["draft", ["submit"]],
    ["pending_approval", []],
    // 回归（复测）：审批后没发送前没有撤回修改的路径
    ["approved", ["revise", "send"]],
    ["sent", ["reject", "accept"]],
    ["accepted", []],
    ["rejected", []],
    ["closed", []],
  ]
  it.each(cases)("%s → %j", (status, actions) => {
    expect(availableQuoteActions(status)).toEqual(actions)
  })

  it("主按钮取最后一个可用操作", () => {
    expect(primaryQuoteAction("sent")).toBe("accept")
    expect(primaryQuoteAction("draft")).toBe("submit")
    expect(primaryQuoteAction("accepted")).toBeNull()
  })

  it("过了有效期：不能再发送 / 客户接受，只剩续期（已发送的还能标客户拒绝）", () => {
    expect(availableQuoteActions("approved", true)).toEqual(["renew"])
    expect(availableQuoteActions("sent", true)).toEqual(["reject", "renew"])
    expect(primaryQuoteAction("sent", true)).toBe("renew")
    expect(availableQuoteActions("draft", true)).toEqual(["submit"])
  })
})

describe("canCopyRevision", () => {
  // 回归（复测）：已发送的报价发现漏项、客户要求调整，只能重新建单
  it("已发送 / 客户拒绝可以复制为新版本；已有修订中的新版本时不再复制", () => {
    expect(canCopyRevision({ status: "sent" })).toBe(true)
    expect(canCopyRevision({ status: "rejected", revisions: [] })).toBe(true)
    expect(canCopyRevision({ status: "approved" })).toBe(false)
    const open = [{ id: "n", code: "Q-2", status: "draft" as const }]
    expect(canCopyRevision({ status: "sent", revisions: open })).toBe(false)
    const done = [{ id: "n", code: "Q-2", status: "closed" as const }]
    expect(canCopyRevision({ status: "rejected", revisions: done })).toBe(true)
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
