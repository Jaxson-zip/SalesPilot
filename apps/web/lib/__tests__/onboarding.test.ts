import { describe, expect, it } from "vitest"

import { guideKeys, PAGE_TIPS, tipKey } from "@/lib/onboarding"

describe("页面首次提示", () => {
  it("每个页面的提示单独记", () => {
    expect(tipKey("ai")).toBe("sp.tip.ai")
    expect(tipKey("ai")).not.toBe(tipKey("quotes"))
    expect(Object.keys(PAGE_TIPS)).toEqual(["ai", "pipeline", "quotes"])
    expect(guideKeys()).toEqual(["sp.tip.ai", "sp.tip.pipeline", "sp.tip.quotes"])
  })
})
