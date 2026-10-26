import { describe, expect, it } from "vitest"

import { EMPTY_CUSTOMER_FORM, toCustomerCreate } from "@/lib/customer"

describe("toCustomerCreate", () => {
  it("名称必填", () => {
    const r = toCustomerCreate({ ...EMPTY_CUSTOMER_FORM, name: "  " })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.errors.name).toBe("请填写客户名称")
  })

  it("只带填写的字段，年度预算元 → 分，去掉首尾空格", () => {
    const r = toCustomerCreate({
      ...EMPTY_CUSTOMER_FORM,
      name: " 深圳明理律所 ",
      industry: "法律",
      level: "A",
      annual_budget: "400,000.5",
    })
    expect(r).toEqual({
      ok: true,
      value: { name: "深圳明理律所", level: "A", industry: "法律", annual_budget: 40000050 },
    })
  })

  it("预算格式错误、字段超长时报错", () => {
    const r = toCustomerCreate({ ...EMPTY_CUSTOMER_FORM, name: "x", annual_budget: "abc", industry: "a".repeat(51) })
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.errors.annual_budget).toBeDefined()
      expect(r.errors.industry).toBe("不能超过 50 个字")
    }
  })
})
