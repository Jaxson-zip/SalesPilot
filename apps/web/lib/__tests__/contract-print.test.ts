import { describe, expect, it } from "vitest"

import { contractDocTitle, planGap, planRatio } from "@/lib/contract-print"

describe("合同要素确认单", () => {
  it("文件名带合同编号和客户", () => {
    expect(contractDocTitle({ code: "C-2026-001", customer: { id: "c", name: "明理律所" } })).toBe(
      "合同要素确认单-C-2026-001-明理律所",
    )
    expect(contractDocTitle({ code: "C-2026-002", customer: null })).toBe("合同要素确认单-C-2026-002")
  })

  it("每期比例与合计核对", () => {
    expect(planRatio(30_000, 100_000)).toBe("30%")
    expect(planRatio(1, 0)).toBe("—")
    expect(planGap([{ amount: 30_000 }, { amount: 60_000 }, { amount: 10_000 }], 100_000)).toBe(0)
    expect(planGap([{ amount: 30_000 }], 100_000)).toBe(70_000)
  })
})
