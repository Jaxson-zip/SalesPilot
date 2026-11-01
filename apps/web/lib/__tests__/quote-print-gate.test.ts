import { describe, expect, it } from "vitest"

import { canPrintQuote } from "@/lib/quote-print"

describe("canPrintQuote", () => {
  it("回归：未审批的报价单不能打印（原来草稿、待审批也能打出 PDF 发给客户）", () => {
    for (const s of ["draft", "pending_approval", "rejected"]) expect(canPrintQuote(s), s).toBe(false)
  })

  it("审批通过、已发送、客户已接受可以打印", () => {
    for (const s of ["approved", "sent", "accepted"]) expect(canPrintQuote(s), s).toBe(true)
  })
})
