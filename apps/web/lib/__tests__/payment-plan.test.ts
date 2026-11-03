import { describe, expect, it } from "vitest"

import { checkPlan, planFullyPaid, planNeedsReason, rowsTotal, toRows } from "@/lib/payment-plan"
import type { PaymentPlanItem, PaymentPlanView } from "@/types/api"

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

  // 回归：已收齐 / 收了一部分的期次原来能删、能改，到账冲抵到哪一期会跟着变
  const item = (patch: Partial<PaymentPlanItem>): PaymentPlanItem => ({
    seq: 1,
    name: "预付款",
    amount: 300_000,
    due_date: "2026-11-01",
    paid: 0,
    status: "pending",
    overdue_days: 0,
    ...patch,
  })

  it("已收款、已开票的期次带上锁定标记", () => {
    const [paid, partial, invoiced] = toRows([
      item({ status: "paid", paid: 300_000 }),
      item({ status: "partial", paid: 100_000 }),
      item({ invoice_status: "requested" }),
    ])
    expect([paid?.lock, partial?.lock, invoiced?.lock]).toEqual(["paid", "partial", "invoiced"])
    expect(partial?.paid).toBe(100_000)
  })

  it("收了一部分的期次金额不能低于已收", () => {
    const r = checkPlan([{ ...rows[0], amount: "500", lock: "partial", paid: 100_000 }], 50_000)
    expect(r).toMatchObject({ ok: false, error: "第 1 期已收 ¥1,000，金额不能低于已收" })
  })

  it("合同已有回款、逾期或开票时要写原因", () => {
    const plan = (items: PaymentPlanItem[], paid_amount = 0) =>
      ({
        contract_id: "c",
        code: "C-1",
        amount: 300_000,
        paid_amount,
        overdue_amount: 0,
        items,
        rule_ref: "",
      }) as PaymentPlanView
    expect(planNeedsReason(plan([item({})]))).toBe(false)
    expect(planNeedsReason(plan([item({})], 1))).toBe(true)
    expect(planNeedsReason(plan([item({ status: "overdue" })]))).toBe(true)
    expect(planNeedsReason(plan([item({ invoice_status: "issued" })]))).toBe(true)
    expect(planFullyPaid(plan([item({ status: "paid" })]))).toBe(true)
    expect(checkPlan([rows[0]], 300_000, " ", true)).toMatchObject({
      error: "这份合同已有回款、逾期或开票，请写明调整原因",
    })
    expect(checkPlan([rows[0]], 300_000, " 客户延期 ", true)).toMatchObject({ ok: true, value: { reason: "客户延期" } })
  })
})
