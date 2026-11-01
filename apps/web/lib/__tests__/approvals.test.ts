import { describe, expect, it } from "vitest"

import {
  approvalAmountText,
  filterApprovals,
  pendingApprovalId,
  pendingCardHint,
  pendingCardHref,
  sortApprovals,
  summarizeApprovals,
} from "@/lib/approvals"
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
      amountByType: { quote: 3_720_000, expense: 206_000 },
      over: 36_000,
      byType: { expense: 2, quote: 1 },
    })
  })

  it("回归：报价金额和报销金额分开显示，不混成一个合计（原来 ¥298,000 报价 + ¥860 报销显示 ¥298,860）", () => {
    const items = [
      item({ id: "q", type: "quote", amount: 29_800_000, at: "2026-05-01T00:00:00Z" }),
      item({ id: "e", amount: 86_000, at: "2026-05-02T00:00:00Z" }),
    ]
    expect(approvalAmountText(summarizeApprovals(items))).toBe("报价 ¥298,000 · 报销 ¥860")
    expect(approvalAmountText(summarizeApprovals(items.slice(1)))).toBe("报销 ¥860")
  })
})

describe("pendingApprovalId", () => {
  const q = {
    status: "pending_approval",
    approvals: [
      { id: "old", status: "rejected" },
      { id: "now", status: "pending" },
    ],
  }

  it("主管看待审批报价：定位到待处理的那条审批", () => {
    expect(pendingApprovalId(q, true)).toBe("now")
  })

  it("不是主管、或报价不在待审批：没有入口", () => {
    expect(pendingApprovalId(q, false)).toBeNull()
    expect(pendingApprovalId({ ...q, status: "approved" }, true)).toBeNull()
  })
})

describe("工作台审批卡片", () => {
  it("回归：点「审批中」能进到对应明细（主管去审批中心，销售去待审批的报价或报销）", () => {
    const both = { pending_approvals: 2, pending_quotes: 1, pending_expenses: 1 }
    expect(pendingCardHref("manager", both)).toBe("/approvals")
    expect(pendingCardHref("sales", both)).toBe("/quotes?view=pending_approval")
    expect(pendingCardHref("sales", { pending_approvals: 1, pending_quotes: 0, pending_expenses: 1 })).toBe(
      "/expenses?view=pending_approval",
    )
    expect(pendingCardHref("sales", { pending_approvals: 0 })).toBeUndefined()
  })

  it("说明行分开写报价和报销各几张", () => {
    expect(pendingCardHint("sales", { pending_quotes: 1, pending_expenses: 2 })).toBe(
      "你提交、等待主管审批：报价 1 · 报销 2",
    )
    expect(pendingCardHint("manager", undefined)).toBe("需要你处理")
  })
})
