import { describe, expect, it } from "vitest"

import { defaultScope, resolveScope, scopeOptions } from "@/lib/views"

describe("数据范围视图", () => {
  it("按角色给出选项", () => {
    expect(scopeOptions("sales", "商机").map((o) => o.value)).toEqual(["mine"])
    expect(scopeOptions("manager", "商机").map((o) => o.label)).toEqual(["团队商机", "我负责的"])
    expect(scopeOptions("admin", "商机")[0].value).toBe("all")
  })
  it("默认范围与回落", () => {
    expect(defaultScope("sales")).toBe("mine")
    expect(defaultScope("manager")).toBe("team")
    expect(resolveScope("sales", "team")).toBe("mine")
    expect(resolveScope("manager", "mine")).toBe("mine")
    expect(resolveScope("manager", "all")).toBe("team")
  })
})
