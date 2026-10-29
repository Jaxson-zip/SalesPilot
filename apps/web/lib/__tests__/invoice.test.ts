import { describe, expect, it } from "vitest"

import { invoiceActions, invoiceDetail } from "@/lib/invoice"
import type { PaymentPlanItem } from "@/types/api"

const item = (extra: Partial<PaymentPlanItem>): PaymentPlanItem => ({
  seq: 1,
  name: "预付款",
  amount: 100,
  due_date: "2026-11-01",
  paid: 0,
  status: "pending",
  overdue_days: 0,
  ...extra,
})

describe("开票跟踪", () => {
  it("负责人只能申请；主管登记或作废", () => {
    const owner = { owner: true, manager: false }
    const manager = { owner: false, manager: true }
    expect(invoiceActions(item({ invoice_status: "none" }), owner)).toEqual(["request"])
    expect(invoiceActions(item({ invoice_status: "requested" }), owner)).toEqual([])
    expect(invoiceActions(item({ invoice_status: "none" }), manager)).toEqual(["issue"])
    expect(invoiceActions(item({ invoice_status: "requested" }), manager)).toEqual(["issue", "void"])
    expect(invoiceActions(item({ invoice_status: "issued" }), manager)).toEqual(["void"])
    expect(invoiceActions(item({}), owner)).toEqual(["request"]) // 老数据没有字段按未开票
  })

  it("说明文字：已开票带号码和未收齐天数，已申请带类型和备注", () => {
    expect(
      invoiceDetail(
        item({ invoice_status: "issued", invoice_type: "special", invoice_no: "No.1", invoiced_unpaid_days: 12 }),
      ),
    ).toBe("专票 No.1 · 开票 12 天未收齐")
    expect(invoiceDetail(item({ invoice_status: "requested", invoice_type: "normal", invoice_note: "抬头 A" }))).toBe(
      "普票 · 抬头 A",
    )
    expect(invoiceDetail(item({ invoice_status: "none" }))).toBe("")
  })
})
