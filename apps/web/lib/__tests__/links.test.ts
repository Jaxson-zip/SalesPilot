import { describe, expect, it } from "vitest"

import { opportunityExpensesHref, subjectHref } from "@/lib/links"

describe("记录页链接", () => {
  it("按对象类型打开那一条", () => {
    expect(subjectHref("customer", "c1")).toBe("/customers/c1")
    expect(subjectHref("opportunity", "o1")).toBe("/pipeline?opp=o1")
    expect(subjectHref("quote", "q1")).toBe("/quotes/q1")
    expect(subjectHref("contract", "k1")).toBe("/contracts?plan=k1")
    expect(subjectHref("expense", "e1")).toBe("/expenses?id=e1")
    expect(subjectHref("approval", "a1")).toBeNull()
  })

  it("商机的跟单费用只看这一单", () => {
    expect(opportunityExpensesHref("o 1")).toBe("/expenses?opp=o%201")
  })
})
