import { describe, expect, it } from "vitest"

import { pickSelected, pruneSelection, selectionLabel } from "@/lib/selection"

const rows = [{ id: "a" }, { id: "b" }, { id: "c" }]
const id = (r: { id: string }) => r.id

describe("表格多选（U1）", () => {
  it("只返回当前可见且被勾选的行，按行顺序", () => {
    expect(pickSelected(rows, { c: true, a: true }, id).map(id)).toEqual(["a", "c"])
  })
  it("切换视图 / 筛选后看不到的行不算选中", () => {
    expect(pickSelected(rows.slice(0, 1), { a: true, c: true }, id).map(id)).toEqual(["a"])
  })
  it("false 值不算选中", () => {
    expect(pickSelected(rows, { a: false }, id)).toEqual([])
  })
  it("pruneSelection 只保留可见行", () => {
    expect(pruneSelection(rows.slice(1), { a: true, b: true }, id)).toEqual({ b: true })
  })
  it("批量栏文案", () => {
    expect(selectionLabel(3)).toBe("已选 3 条")
  })
})
