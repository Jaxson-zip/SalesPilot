import { describe, expect, it } from "vitest"

import {
  discountToInput,
  initialQtyDraft,
  isAdjustDirty,
  parseDiscountPercent,
  previewAdjust,
  toItemsPatch,
} from "@/lib/quote-adjust"

const items = [
  { sku: "gpu", qty: 2, unit_price: 100000 },
  { sku: "svc", qty: 1, unit_price: 50000 },
]

describe("折扣输入", () => {
  it("百分比 → 比例；空 = 0", () => {
    expect(parseDiscountPercent("8")).toBe(0.08)
    expect(parseDiscountPercent("12.5%")).toBe(0.125)
    expect(parseDiscountPercent("")).toBe(0)
  })
  it("非法：≥100、负数、两位小数", () => {
    expect(parseDiscountPercent("100")).toBeNull()
    expect(parseDiscountPercent("-1")).toBeNull()
    expect(parseDiscountPercent("1.25")).toBeNull()
  })
  it("比例 → 输入框", () => {
    expect(discountToInput(0.08)).toBe("8")
    expect(discountToInput(0.125)).toBe("12.5")
    expect(discountToInput(undefined)).toBe("")
  })
})

describe("调价预览（只做展示，保存后以后端为准）", () => {
  it("数量和折扣实时影响合计，折扣四舍五入到分", () => {
    const p = previewAdjust(items, { gpu: "3", svc: "1" }, "8")
    expect(p.valid).toBe(true)
    expect(p.listTotal).toBe(350000)
    expect(p.discountAmount).toBe(28000)
    expect(p.total).toBe(322000)
    expect(p.lines[0]).toEqual({ sku: "gpu", qty: 3, subtotal: 300000 })
  })
  it("非法数量：标记无效，按原数量预览", () => {
    const p = previewAdjust(items, { gpu: "0", svc: "1" }, "")
    expect(p.valid).toBe(false)
    expect(p.listTotal).toBe(250000)
  })
  it("改动检测", () => {
    const draft = initialQtyDraft(items)
    expect(isAdjustDirty(items, draft, "", 0)).toBe(false)
    expect(isAdjustDirty(items, draft, "8", 0.08)).toBe(false)
    expect(isAdjustDirty(items, { ...draft, gpu: "3" }, "", 0)).toBe(true)
    expect(isAdjustDirty(items, draft, "5", 0)).toBe(true)
  })
  it("请求体：{items:[{sku,qty}], discount_rate}；非法返回 null", () => {
    expect(toItemsPatch(items, { gpu: "3", svc: "1" }, "8")).toEqual({
      items: [
        { sku: "gpu", qty: 3 },
        { sku: "svc", qty: 1 },
      ],
      discount_rate: 0.08,
    })
    expect(toItemsPatch(items, { gpu: "x" }, "8")).toBeNull()
    expect(toItemsPatch(items, {}, "120")).toBeNull()
  })
})
