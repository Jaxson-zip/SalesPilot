import { describe, expect, it } from "vitest"

import { fenToYuanInput, parsePositiveInt, yuanToFen } from "@/lib/money"

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
