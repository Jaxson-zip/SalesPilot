import { describe, expect, it } from "vitest"

import { guideKeys, PAGE_TIPS, progressPercent, showOnboarding, tipKey } from "@/lib/onboarding"

describe("新手引导", () => {
  it("做完、没加载或收起后不显示清单", () => {
    expect(showOnboarding({ done: 1, total: 4 }, false)).toBe(true)
    expect(showOnboarding({ done: 4, total: 4 }, false)).toBe(false)
    expect(showOnboarding({ done: 0, total: 0 }, false)).toBe(false)
    expect(showOnboarding(undefined, false)).toBe(false)
    expect(showOnboarding({ done: 1, total: 4 }, true)).toBe(false)
  })

  it("进度百分比", () => {
    expect(progressPercent(1, 4)).toBe(25)
    expect(progressPercent(2, 3)).toBe(67)
    expect(progressPercent(5, 4)).toBe(100)
    expect(progressPercent(0, 0)).toBe(0)
  })

  it("每个页面的提示单独记", () => {
    expect(tipKey("ai")).toBe("sp.tip.ai")
    expect(tipKey("ai")).not.toBe(tipKey("quotes"))
    expect(Object.keys(PAGE_TIPS)).toEqual(["ai", "pipeline", "quotes"])
    expect(guideKeys()).toEqual(["sp.onboarding.dismissed", "sp.tip.ai", "sp.tip.pipeline", "sp.tip.quotes"])
  })
})
