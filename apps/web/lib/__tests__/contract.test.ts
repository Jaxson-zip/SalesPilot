import { describe, expect, it } from "vitest"

import { checkPayment, contractHref, newRequestKey, paidPercent, suggestedPayment, unpaidOf } from "@/lib/contract"

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

describe("登记回款预填金额", () => {
  const next = {
    name: "签约首付款",
    amount: 2_760_000,
    due_date: "2026-11-01",
    status: "pending" as const,
    overdue_days: 0,
  }
  it("按下一期没收的金额预填，不超过未回款", () => {
    expect(suggestedPayment({ amount: 9_200_000, paid_amount: 0, next_payment: next })).toBe("27600")
    expect(suggestedPayment({ amount: 9_200_000, paid_amount: 9_000_000, next_payment: next })).toBe("2000")
  })
  it("没有回款计划时预填全部未回款，已收齐为空", () => {
    expect(suggestedPayment({ amount: 10_050, paid_amount: 0, next_payment: null })).toBe("100.50")
    expect(suggestedPayment({ amount: 100, paid_amount: 100, next_payment: null })).toBe("")
  })
})

describe("newRequestKey", () => {
  it("每次打开登记框不同，长度符合后端 8～100", () => {
    const a = newRequestKey()
    expect(a).not.toBe(newRequestKey())
    expect(a.length).toBeGreaterThanOrEqual(8)
    expect(a.length).toBeLessThanOrEqual(100)
  })
})
