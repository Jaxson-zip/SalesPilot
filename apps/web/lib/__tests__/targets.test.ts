import { describe, expect, it } from "vitest"

import { changedItems, gapText, monthLabel, pace, parseWan, shiftMonth, toWan, type TargetRow } from "@/lib/targets"

const row = (id: string, target: number | null): TargetRow => ({
  user: { id, name: id },
  role: "sales",
  team_name: null,
  active: true,
  target,
  achieved: 0,
  contracts: 0,
  forecast: 0,
  rate: null,
})

describe("业绩目标", () => {
  it("月份切换跨年", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01")
    expect(shiftMonth("2026-01", -1)).toBe("2025-12")
    expect(monthLabel("2026-03")).toBe("2026 年 3 月")
  })

  it("完成率和时间进度比较", () => {
    expect(pace(null, 0.5)).toBe("none")
    expect(pace(1.02, 0.5)).toBe("done")
    expect(pace(0.5, 0.5)).toBe("ahead")
    expect(pace(0.3, 0.5)).toBe("behind")
  })

  it("还差 / 超出", () => {
    expect(gapText(null, 100)).toBe("")
    expect(gapText(10_000_00, 4_000_00)).toBe("还差 ¥6,000")
    expect(gapText(10_000_00, 12_000_00)).toBe("超出 ¥2,000")
  })

  it("目标按万元输入：换算成分，空为清除，非法为 undefined", () => {
    expect(parseWan("50")).toBe(50_000_000)
    expect(parseWan("12.5")).toBe(12_500_000)
    expect(parseWan(" ")).toBeNull()
    expect(parseWan("-1")).toBeUndefined()
    expect(parseWan("abc")).toBeUndefined()
    expect(toWan(12_500_000)).toBe("12.5")
    expect(toWan(null)).toBe("")
  })

  it("只提交改过且合法的", () => {
    const rows = [row("a", 50_000_000), row("b", null), row("c", 10_000_000), row("d", null)]
    expect(changedItems(rows, { a: "50", b: "30", c: "", d: "x" })).toEqual([
      { user_id: "b", amount: 30_000_000 },
      { user_id: "c", amount: null },
    ])
  })
})
