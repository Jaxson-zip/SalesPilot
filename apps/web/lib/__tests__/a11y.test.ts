import { describe, expect, it } from "vitest"

import { comboLabel } from "@/lib/a11y"

describe("comboLabel", () => {
  it("字段名在前，包含控件上显示的文字", () => {
    expect(comboLabel("发生日期", "2026-11-05")).toBe("发生日期：2026-11-05")
    expect(comboLabel("关联客户", "搜索并选择客户")).toContain("搜索并选择客户")
  })

  it("没有显示文字时只读字段名", () => {
    expect(comboLabel("客户", "  ")).toBe("客户")
  })
})
