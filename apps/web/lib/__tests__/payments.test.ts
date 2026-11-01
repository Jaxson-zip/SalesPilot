import { describe, expect, it } from "vitest"

import { canReversePayment, checkReverseReason, paymentDetail, paymentKind } from "@/lib/payments"
import type { PaymentRecord } from "@/types/api"

const base: PaymentRecord = {
  id: "p1",
  amount: 100_00,
  received_on: "2026-10-30",
  reference_no: "BK-001",
  note: "首付款",
  reversal_of: null,
  reversed_by: null,
  reason: null,
  created_by: { id: "u", name: "张主管" },
  created_at: "2026-10-30T10:00:00Z",
}

describe("回款记录", () => {
  it("区分正常、已冲正、冲正记录；只有主管能冲正正常的那笔", () => {
    const reversed = { ...base, reversed_by: "p2" }
    const reversal = { ...base, id: "p2", amount: -100_00, reversal_of: "p1", reason: "金额录错" }
    expect([base, reversed, reversal].map(paymentKind)).toEqual(["normal", "reversed", "reversal"])
    expect(canReversePayment(base, true)).toBe(true)
    expect(canReversePayment(base, false)).toBe(false)
    expect(canReversePayment(reversed, true)).toBe(false)
    expect(canReversePayment(reversal, true)).toBe(false)
    expect(paymentDetail(reversal)).toBe("2026-10-30 · 流水号 BK-001 · 冲正原因：金额录错")
  })

  it("说明行省略缺的项", () => {
    expect(paymentDetail({ ...base, reference_no: null, note: null })).toBe("2026-10-30")
  })

  it("冲正原因至少 2 个字", () => {
    expect(checkReverseReason(" 错 ")).toBeTruthy()
    expect(checkReverseReason("金额录错")).toBeUndefined()
    expect(checkReverseReason("x".repeat(201))).toBeTruthy()
  })
})
