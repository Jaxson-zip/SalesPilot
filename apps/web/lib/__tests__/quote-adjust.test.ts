import { describe, expect, it } from "vitest"

import {
  discountToInput,
  initialDraft,
  isAdjustDirty,
  isExtraSku,
  newExtraRow,
  parseDiscountPercent,
  previewAdjust,
  toItemsPatch,
  type DraftRow,
} from "@/lib/quote-adjust"

const items = [
  { sku: "gpu", name: "显卡", unit: "台", qty: 2, unit_price: 100000, unit_cost: 60000 },
  { sku: "svc", name: "实施", unit: "项", qty: 1, unit_price: 50000, unit_cost: 0 },
]

const withQty = (rows: DraftRow[], sku: string, qty: string) => rows.map((r) => (r.sku === sku ? { ...r, qty } : r))

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
    const p = previewAdjust(withQty(initialDraft(items), "gpu", "3"), "8")
    expect(p.valid).toBe(true)
    expect(p.listTotal).toBe(350000)
    expect(p.discountAmount).toBe(28000)
    expect(p.total).toBe(322000)
    expect(p.lines[0]).toEqual({ sku: "gpu", qty: 3, subtotal: 300000 })
  })
  it("非法数量：标记无效", () => {
    expect(previewAdjust(withQty(initialDraft(items), "gpu", "0"), "").valid).toBe(false)
  })
  it("改动检测", () => {
    const draft = initialDraft(items)
    expect(isAdjustDirty(items, draft, "", 0)).toBe(false)
    expect(isAdjustDirty(items, draft, "8", 0.08)).toBe(false)
    expect(isAdjustDirty(items, withQty(draft, "gpu", "3"), "", 0)).toBe(true)
    expect(isAdjustDirty(items, draft, "5", 0)).toBe(true)
    expect(isAdjustDirty(items, [...draft, newExtraRow()], "", 0)).toBe(true)
  })
  it("请求体：目录物料只带 sku + 数量；非法返回 null", () => {
    expect(toItemsPatch(withQty(initialDraft(items), "gpu", "3"), "8")).toEqual({
      items: [
        { sku: "gpu", qty: 3 },
        { sku: "svc", qty: 1 },
      ],
      discount_rate: 0.08,
    })
    expect(toItemsPatch(withQty(initialDraft(items), "gpu", "x"), "8")).toBeNull()
    expect(toItemsPatch(initialDraft(items), "120")).toBeNull()
  })
})

describe("自己加的费用", () => {
  it("新行是 extra- 开头，名称和单价必填，成本可不填", () => {
    const row = newExtraRow()
    expect(isExtraSku(row.sku)).toBe(true)
    expect(newExtraRow().sku).not.toBe(row.sku)
    const rows = [...initialDraft(items), row]
    expect(previewAdjust(rows, "").valid).toBe(false)
    expect(previewAdjust([...initialDraft(items), { ...row, name: "加急费" }], "").valid).toBe(false)
    const filled = [...initialDraft(items), { ...row, name: " 加急费 ", price: "1,000", qty: "2" }]
    const p = previewAdjust(filled, "")
    expect(p.valid).toBe(true)
    expect(p.listTotal).toBe(250000 + 200000)
    expect(toItemsPatch(filled, "")?.items[2]).toEqual({
      sku: row.sku,
      qty: 2,
      name: "加急费",
      unit: "项",
      unit_price: 100000,
      unit_cost: 0,
    })
  })
  it("已保存的费用行回填名称、单价、成本", () => {
    const saved = { sku: "extra-a", name: "差旅", unit: "次", qty: 2, unit_price: 30050, unit_cost: 25000 }
    expect(initialDraft([saved])[0]).toEqual({
      sku: "extra-a",
      name: "差旅",
      unit: "次",
      qty: "2",
      price: "300.50",
      cost: "250",
      extra: true,
    })
    expect(isAdjustDirty([saved], initialDraft([saved]), "", 0)).toBe(false)
  })
})
