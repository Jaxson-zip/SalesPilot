import { describe, expect, it } from "vitest"

import { toOpportunityCreate, type OpportunityFormValues } from "@/lib/opportunity"

const base: OpportunityFormValues = {
  customer_id: "c1",
  name: " 合同审查私有化 ",
  amount: "372000",
  win_rate: "",
  expected_close_date: "2026-11-15",
  product_line_id: "pl1",
}

describe("toOpportunityCreate", () => {
  it("金额转分，空赢率不传（后端默认 10）", () => {
    expect(toOpportunityCreate(base)).toEqual({
      ok: true,
      value: {
        customer_id: "c1",
        name: "合同审查私有化",
        amount: 37200000,
        expected_close_date: "2026-11-15",
        product_line_id: "pl1",
      },
    })
  })

  it("赢率 0–100，0 元商机允许", () => {
    const r = toOpportunityCreate({
      ...base,
      amount: "0",
      win_rate: "60",
      product_line_id: null,
      expected_close_date: "",
    })
    expect(r).toEqual({ ok: true, value: { customer_id: "c1", name: "合同审查私有化", amount: 0, win_rate: 60 } })
    expect(toOpportunityCreate({ ...base, win_rate: "120" }).ok).toBe(false)
  })

  it("缺客户、名称、金额时报错", () => {
    const r = toOpportunityCreate({ ...base, customer_id: null, name: "", amount: "x" })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(Object.keys(r.errors).sort()).toEqual(["amount", "customer_id", "name"])
  })
})
