import { describe, expect, it } from "vitest"

import { historyTime } from "@/lib/thread-history"
import { scopeLabel } from "@/lib/views"

describe("审查 v6 待定项", () => {
  it("会话记录时间：今天显示时分，更早显示月-日", () => {
    const now = new Date(2026, 9, 28, 18, 0)
    expect(historyTime(new Date(2026, 9, 28, 9, 5).getTime(), now)).toBe("09:05")
    expect(historyTime(new Date(2026, 9, 26, 23, 59).getTime(), now)).toBe("10-26")
    expect(historyTime(0, now)).toBe("")
  })

  it("视图名随数据范围", () => {
    expect(scopeLabel("sales", "报价单")).toBe("我的报价单")
    expect(scopeLabel("manager", "合同")).toBe("团队合同")
    expect(scopeLabel("admin", "报价单")).toBe("全部报价单")
  })
})
