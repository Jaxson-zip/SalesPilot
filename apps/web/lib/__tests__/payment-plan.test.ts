import { describe, expect, it } from "vitest"

import { checkPlan, rowsTotal, toRows } from "@/lib/payment-plan"

const rows = [
  { name: "预付款", amount: "3000", due_date: "2026-11-01" },
  { name: "尾款", amount: "7000", due_date: "2027-01-01" },
]

describe("回款计划编辑", () => {
  it("合计等于合同金额时转成分", () => {
    expect(checkPlan(rows, 1_000_000)).toEqual({
      ok: true,
      value: {
        items: [
          { name: "预付款", amount: 300_000, due_date: "2026-11-01" },
          { name: "尾款", amount: 700_000, due_date: "2027-01-01" },
        ],
      },
    })
    expect(rowsTotal(rows)).toBe(1_000_000)
  })

  it("合计不等时写明差多少", () => {
    const r = checkPlan(rows, 1_200_000)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain("还差 ¥2,000")
    const over = checkPlan(rows, 900_000)
    if (!over.ok) expect(over.error).toContain("多了 ¥1,000")
  })

  it("逐行校验名称、金额、日期", () => {
    expect(checkPlan([{ ...rows[0], name: " " }], 300_000)).toMatchObject({ error: "第 1 期没有填写名称" })
    expect(checkPlan([{ ...rows[0], amount: "0" }], 300_000)).toMatchObject({ ok: false })
    expect(checkPlan([{ ...rows[0], due_date: "" }], 300_000)).toMatchObject({ error: "第 1 期没有填写到期日" })
    expect(checkPlan([], 0)).toMatchObject({ error: "至少需要一期" })
  })

  it("接口数据转表单行（分 → 元）", () => {
    const items = [
      {
        seq: 1,
        name: "预付款",
        amount: 12_345,
        due_date: "2026-11-01",
        paid: 0,
        status: "pending" as const,
        overdue_days: 0,
      },
    ]
    expect(toRows(items)).toEqual([{ name: "预付款", amount: "123.45", due_date: "2026-11-01" }])
  })
})
