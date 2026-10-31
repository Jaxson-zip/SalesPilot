import { describe, expect, it } from "vitest"

import { checkPayment, contractHref, paidPercent, unpaidOf } from "@/lib/contract"

describe("合同回款", () => {
  const c = { amount: 81000000, paid_amount: 32400000 }

  it("进度百分比夹紧到 0–100", () => {
    expect(paidPercent(0.4)).toBe(40)
    expect(paidPercent(1.2)).toBe(100)
    expect(paidPercent(-1)).toBe(0)
    expect(paidPercent(Number.NaN)).toBe(0)
  })

  it("未回款金额", () => {
    expect(unpaidOf(c)).toBe(48600000)
    expect(unpaidOf({ amount: 1, paid_amount: 5 })).toBe(0)
  })

  it("登记回款前校验", () => {
    expect(checkPayment("100000", c)).toEqual({ ok: true, amount: 10000000 })
    expect(checkPayment("486000", c)).toEqual({ ok: true, amount: 48600000 })
    expect(checkPayment("486000.01", c)).toEqual({ ok: false, error: "超过未回款金额 ¥486,000" })
    expect(checkPayment("0", c).ok).toBe(false)
  })
})

describe("合同跳转", () => {
  it("报价「查看合同」直接打开这一份合同", () => {
    expect(contractHref("c-1")).toBe("/contracts?plan=c-1")
  })
})
