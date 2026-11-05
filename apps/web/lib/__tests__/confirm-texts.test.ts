import { describe, expect, it } from "vitest"

import { expenseOverTitle } from "@/lib/confirm-texts"

// 回归：「其他」类 ¥0.01 的草稿只写「需主管审批」，看不出为什么
describe("expenseOverTitle", () => {
  it("没超标也要审批时说明是因为制度里没有标准", () => {
    expect(expenseOverTitle(0, false)).toBe("制度里没有标准，不论金额大小都需主管审批")
    expect(expenseOverTitle(100, false)).toBe("超出报销标准，需主管审批")
  })
})
