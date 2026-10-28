import { describe, expect, it } from "vitest"

import { parseInline, toInlineText } from "@/lib/inline-edit"

describe("行内编辑取值", () => {
  it("金额：元 → 分；可清空字段空串 → null；必填字段不能空", () => {
    expect(parseInline("1,234.5", { kind: "money" })).toEqual({ ok: true, value: 123_450 })
    expect(parseInline(" ", { kind: "money" })).toEqual({ ok: true, value: null })
    expect(parseInline("", { kind: "money", required: true })).toEqual({ ok: false, error: "不能为空" })
    expect(parseInline("abc", { kind: "money" }).ok).toBe(false)
  })

  it("整数范围（赢率 0–100）", () => {
    expect(parseInline("60", { kind: "int", min: 0, max: 100 })).toEqual({ ok: true, value: 60 })
    expect(parseInline("120", { kind: "int", min: 0, max: 100 })).toEqual({ ok: false, error: "请输入 0–100 的整数" })
    expect(parseInline("3.5", { kind: "int", min: 0, max: 100 }).ok).toBe(false)
  })

  it("文本去掉首尾空格；分 → 编辑框文字", () => {
    expect(parseInline("  南山区 ", { kind: "text" })).toEqual({ ok: true, value: "南山区" })
    expect(toInlineText(123_450, "money")).toBe("1234.50")
    expect(toInlineText(null, "text")).toBe("")
  })
})
