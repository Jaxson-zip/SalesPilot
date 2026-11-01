import { describe, expect, it } from "vitest"

import { QUICK_START } from "@/lib/help-content"

describe("管理员使用说明", () => {
  it("回归：界面能改的配置链接到配置页，不再让人去改 rules.yaml", () => {
    const steps = QUICK_START.admin.steps
    const hrefs = steps.flatMap((s) => (typeof s === "string" ? [] : [s.href]))
    expect(hrefs).toEqual(expect.arrayContaining(["/settings/rules", "/settings/packs"]))
    const text = steps.map((s) => (typeof s === "string" ? s : s.text)).join("\n")
    expect(text).not.toContain("rules.yaml")
    expect(text).not.toContain("产品与定价") // 页面已改名为「行业包与产品」
  })
})
