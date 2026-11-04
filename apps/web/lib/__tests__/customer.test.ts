import { describe, expect, it } from "vitest"

import { createCustomerLabel, EMPTY_CUSTOMER_FORM, toCustomerCreate } from "@/lib/customer"

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

// 回归：新建商机 / 报价 / 报销时客户还没建，只能关掉表单去客户页
describe("选择客户时的新建入口", () => {
  it("带上输入的名称，太长截断；没输入只写「新建客户」", () => {
    expect(createCustomerLabel("  走查科技 ")).toBe("新建客户「走查科技」")
    expect(createCustomerLabel("")).toBe("新建客户")
    expect(createCustomerLabel("一".repeat(25))).toBe(`新建客户「${"一".repeat(20)}…」`)
  })
})
