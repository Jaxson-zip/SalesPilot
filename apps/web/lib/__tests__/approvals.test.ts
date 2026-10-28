import { describe, expect, it } from "vitest"

import { filterApprovals, sortApprovals, summarizeApprovals } from "@/lib/approvals"
import type { ApprovalItem } from "@/types/api"

function item(p: {
  id: string
  type?: "quote" | "expense"
  amount: number
  over?: number
  at: string
  owner?: string
  title?: string
}): ApprovalItem {
  return {
    id: p.id,
    target_type: p.type ?? "expense",
    target: {
      id: p.id,
      code: `E-${p.id}`,
      title: p.title ?? "客户招待 · 深圳明理律师事务所",
      amount: p.amount,
      owner: p.owner ? { id: p.owner, name: p.owner } : null,
      over_amount: p.over ?? null,
    },
    reason: "人均超标",
    ai_suggestion: null,
    status: "pending",
    attachments: [],
    created_at: p.at,
  } as ApprovalItem
}

const items = [
  item({ id: "1", amount: 86_000, over: 26_000, at: "2026-10-28T09:00:00Z", owner: "张晨" }),
  item({ id: "2", amount: 120_000, over: 10_000, at: "2026-10-28T08:00:00Z", owner: "王磊" }),
  item({
    id: "3",
    type: "quote",
    amount: 3_720_000,
    at: "2026-10-28T10:00:00Z",
    owner: "张晨",
    title: "鹏城医院 · 标准版报价",
  }),
]

describe("审批列表筛选 / 排序 / 汇总", () => {
  it("按类型和关键词（单号、客户、申请人）筛选", () => {
    expect(filterApprovals(items, "quote", "").map((a) => a.id)).toEqual(["3"])
    expect(filterApprovals(items, "all", "王磊").map((a) => a.id)).toEqual(["2"])
    expect(filterApprovals(items, "expense", "明理").map((a) => a.id)).toEqual(["1", "2"])
    expect(filterApprovals(items, "all", "e-3").map((a) => a.id)).toEqual(["3"])
  })

  it("默认最早提交优先；可按金额、超标排序", () => {
    expect(sortApprovals(items, "oldest").map((a) => a.id)).toEqual(["2", "1", "3"])
    expect(sortApprovals(items, "amount").map((a) => a.id)).toEqual(["3", "2", "1"])
    expect(sortApprovals(items, "over").map((a) => a.id)).toEqual(["1", "2", "3"])
  })

  it("汇总条数、金额、超标合计和各类型数量", () => {
    expect(summarizeApprovals(items)).toEqual({
      count: 3,
      amount: 3_926_000,
      over: 36_000,
      byType: { expense: 2, quote: 1 },
    })
  })
})
