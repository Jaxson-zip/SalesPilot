import { describe, expect, it } from "vitest"

import { TODO_KIND_LABEL, todoCounts, todoWhen } from "@/lib/todos"

describe("待办里的回款 / 日报 / 待审批", () => {
  it("逾期的计入逾期，其余计入今天", () => {
    expect(todoCounts([{ overdue: true }, { overdue: false }, {}])).toEqual({ today: 2, overdue: 1 })
    expect(todoCounts([])).toEqual({ today: 0, overdue: 0 })
  })

  it("右侧时间说明：待审批没有到期日", () => {
    expect(todoWhen({ kind: "payment_overdue", overdue: true })).toBe("已逾期")
    expect(todoWhen({ kind: "payment_due" })).toBe("今天")
    expect(todoWhen({ kind: "report" })).toBe("今天")
    expect(todoWhen({ kind: "approval" })).toBe("")
  })

  it("每种事项都有类型文案", () => {
    expect(TODO_KIND_LABEL.report).toBe("日报")
    expect(TODO_KIND_LABEL.payment_overdue).toBe("回款")
  })
})
