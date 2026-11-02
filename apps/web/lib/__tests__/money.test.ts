import { describe, expect, it } from "vitest"

import { discountedPrice, fenToYuanInput, parsePositiveInt, yuanToFen } from "@/lib/money"

describe("yuanToFen（表单元 → 分）", () => {
  it("整数、小数、千分位", () => {
    expect(yuanToFen("860")).toBe(86000)
    expect(yuanToFen("0.1")).toBe(10)
    expect(yuanToFen("1,234.5")).toBe(123450)
    expect(yuanToFen("¥ 19.99")).toBe(1999)
  })
  it("不产生浮点误差", () => {
    expect(yuanToFen("1.15")).toBe(115)
    expect(yuanToFen("4.35")).toBe(435)
  })
  it("非法输入返回 null", () => {
    expect(yuanToFen("")).toBeNull()
    expect(yuanToFen("abc")).toBeNull()
    expect(yuanToFen("1.234")).toBeNull()
    expect(yuanToFen("-5")).toBeNull()
  })
})

describe("fenToYuanInput / parsePositiveInt", () => {
  it("分 → 输入框文字", () => {
    expect(fenToYuanInput(86000)).toBe("860")
    expect(fenToYuanInput(123450)).toBe("1234.50")
    expect(fenToYuanInput(5)).toBe("0.05")
  })
  it("正整数解析带范围", () => {
    expect(parsePositiveInt("4")).toBe(4)
    expect(parsePositiveInt("0")).toBeNull()
    expect(parsePositiveInt("0", { min: 0 })).toBe(0)
    expect(parsePositiveInt("101", { max: 100 })).toBeNull()
    expect(parsePositiveInt("2.5")).toBeNull()
  })
})

describe("discountedPrice（与 core discounted_price 同口径）", () => {
  it("回归：¥1.05 打九折，折扣额 10.5 分半分进位为 11 分，折后 94 分（方案预览曾得到 95）", () => {
    expect(discountedPrice(105, 0.1)).toBe(94)
  })

  it("半分边界和普通情况", () => {
    expect(discountedPrice(115, 0.1)).toBe(103) // 11.5 → 12
    expect(discountedPrice(114, 0.1)).toBe(103) // 11.4 → 11
    expect(discountedPrice(100_000, 0.05)).toBe(95_000)
    expect(discountedPrice(999, 0.0333)).toBe(966) // 33.2667 → 33
    expect(discountedPrice(500, 0)).toBe(500)
  })

  it("大金额不丢精度（100 亿元）", () => {
    expect(discountedPrice(1_000_000_000_000, 0.1234)).toBe(876_600_000_000)
    expect(discountedPrice(999_999_999_999, 0.0001)).toBe(999_899_999_999)
  })
})
