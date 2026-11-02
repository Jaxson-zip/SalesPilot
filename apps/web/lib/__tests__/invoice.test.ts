import { describe, expect, it } from "vitest"

import { invoiceActions, invoiceDetail, invoiceEventText } from "@/lib/invoice"
import type { InvoiceEvent, PaymentPlanItem } from "@/types/api"

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

const event = (extra: Partial<InvoiceEvent>): InvoiceEvent => ({
  seq: 1,
  plan_name: "预付款",
  amount: 100,
  action: "issue",
  from_status: "none",
  invoice_type: "special",
  invoice_no: "No.111",
  invoiced_on: "2026-10-08",
  note: null,
  actor: null,
  created_at: "2026-10-08T02:00:00Z",
  ...extra,
})

describe("开票历史", () => {
  it("作废记录带原票号码、开票日和原因（作废后期次上的字段已清空）", () => {
    const voided = event({ action: "void", from_status: "issued", note: "抬头写错" })
    expect(invoiceEventText(voided)).toBe("作废发票 · 专票 No.111（开票日 2026-10-08） · 原因：抬头写错")
  })
  it("撤回申请、申请、登记", () => {
    const withdraw = event({
      action: "void",
      from_status: "requested",
      invoice_no: null,
      invoiced_on: null,
      note: "客户暂不要",
    })
    expect(invoiceEventText(withdraw)).toBe("撤回开票申请 · 原因：客户暂不要")
    expect(invoiceEventText(event({ action: "request", invoice_type: "normal", note: "抬头 A" }))).toBe(
      "申请开票 · 普票 · 抬头 A",
    )
    expect(invoiceEventText(event({}))).toBe("登记开票 · 专票 No.111")
  })
})
