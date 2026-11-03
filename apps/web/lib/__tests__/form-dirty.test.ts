import { describe, expect, it } from "vitest"

import { changedFrom } from "@/lib/form-dirty"

describe("changedFrom", () => {
  it("没改过、只多了空白都不算修改", () => {
    expect(changedFrom({ name: "", tags: [] }, { name: "", tags: [] })).toBe(false)
    expect(changedFrom({ name: "  " }, { name: "" })).toBe(false)
  })

  it("填了内容、改了列表算修改（回归：新建客户填了资料按 Esc 直接丢失）", () => {
    expect(changedFrom({ name: "明理律所" }, { name: "" })).toBe(true)
    expect(changedFrom({ tags: ["a"] }, { tags: [] })).toBe(true)
    expect(changedFrom({ level: "A" }, { level: null })).toBe(true)
  })
})
