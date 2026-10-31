import { describe, expect, it } from "vitest"

import {
  approvalPreview,
  approvalRules,
  catalogRow,
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
  it("请求体：目录物料带 sku、数量、单价；非法返回 null", () => {
    expect(toItemsPatch(withQty(initialDraft(items), "gpu", "3"), "8")).toEqual({
      items: [
        { sku: "gpu", qty: 3, unit_price: 100000 },
        { sku: "svc", qty: 1, unit_price: 50000 },
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
      basePrice: null,
    })
    expect(isAdjustDirty([saved], initialDraft([saved]), "", 0)).toBe(false)
  })
})

describe("目录物料改单价、从目录添加", () => {
  it("改单价：合计、预估毛利跟着变，请求带新单价", () => {
    const rows = initialDraft(items).map((r) => (r.sku === "gpu" ? { ...r, price: "800" } : r))
    const p = previewAdjust(rows, "")
    expect(p.listTotal).toBe(80000 * 2 + 50000)
    // 成本 1200 元，合计 2100 元
    expect(p.margin).toBeCloseTo((210000 - 120000) / 210000)
    expect(toItemsPatch(rows, "")?.items[0]).toEqual({ sku: "gpu", qty: 2, unit_price: 80000 })
    expect(rows[0].basePrice).toBe(100000)
  })
  it("从目录加一行：目录价和成本", () => {
    const row = catalogRow({ sku: "ssd", name: "SSD", unit: "块", cost: 30000, price: 45050 })
    expect(row).toMatchObject({ sku: "ssd", qty: "1", price: "450.50", cost: "300", extra: false, basePrice: 45050 })
    expect(isAdjustDirty(items, [...initialDraft(items), row], "", 0)).toBe(true)
  })
  it("没有明细不能保存", () => {
    expect(previewAdjust([], "").valid).toBe(false)
    expect(toItemsPatch([], "")).toBeNull()
  })
})

describe("审批预判（和后端规则一致）", () => {
  const rules = { floor: 0.25, maxDiscount: 0.1 }
  const row = (sku: string, price: string, cost: string, extra = false): DraftRow => ({
    sku,
    name: sku,
    unit: "台",
    qty: "1",
    price,
    cost,
    extra,
    basePrice: null,
  })
  const catalog = { "SRV-4": 26_200_000 }

  it("按目录价、毛利达标：自动通过", () => {
    expect(approvalPreview([row("SRV-4", "262000", "150000")], "0", catalog, rules)).toEqual([])
  })
  it("压低单价、折扣填 0：按目录价算出折扣，超出权限要审批", () => {
    const rows = [row("SRV-4", "220000", "150000"), row("extra-x", "100000", "0", true)]
    expect(approvalPreview(rows, "0", catalog, rules)).toEqual(["比目录价低 11.6%，超出销售折扣权限 10%"])
  })
  it("毛利低于底线也提示；输入不合法返回 null", () => {
    expect(approvalPreview([row("SRV-4", "262000", "218000")], "0", catalog, rules)?.[0]).toBe(
      "毛利 16.8% 低于底线 25%",
    )
    expect(approvalPreview([row("SRV-4", "abc", "1")], "0", catalog, rules)).toBeNull()
  })
  it("从行业包规则里读阈值，缺了返回 null", () => {
    expect(approvalRules({ margin: { floor_rate: 0.2 }, discount: { max_rate: 0.15 } })).toEqual({
      floor: 0.2,
      maxDiscount: 0.15,
    })
    expect(approvalRules({ margin: {} })).toBeNull()
  })
})
