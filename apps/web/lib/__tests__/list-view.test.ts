import { describe, expect, it } from "vitest"

import {
  applyFilters,
  fenToYuan,
  filterChips,
  optionsFromRows,
  parseHiddenColumns,
  sortRows,
  toCsv,
  toggleFilter,
  toggleHidden,
  type FilterDef,
  type SortAccessors,
} from "@/lib/list-view"

interface Row {
  id: string
  status: string
  type: string | null
  amount: number
  at: string | null
}

const rows: Row[] = [
  { id: "a", status: "draft", type: "x", amount: 300, at: "2026-10-01T00:00:00Z" },
  { id: "b", status: "sent", type: "y", amount: 100, at: "2026-10-03T00:00:00Z" },
  { id: "c", status: "draft", type: null, amount: 200, at: null },
]

const defs: FilterDef<Row>[] = [
  {
    id: "status",
    label: "状态",
    options: [
      { value: "draft", label: "草稿" },
      { value: "sent", label: "已发送" },
    ],
    get: (r) => r.status,
  },
  { id: "type", label: "类型", options: [{ value: "x", label: "X" }], get: (r) => r.type },
]

const acc: SortAccessors<Row> = { updated: (r) => r.at, amount: (r) => r.amount }

describe("applyFilters", () => {
  it("没有生效筛选时原样返回", () => {
    expect(applyFilters(rows, defs, {})).toBe(rows)
  })
  it("同字段为或、跨字段为且，空值不匹配", () => {
    expect(applyFilters(rows, defs, { status: ["draft", "sent"] }).map((r) => r.id)).toEqual(["a", "b", "c"])
    expect(applyFilters(rows, defs, { status: ["draft"], type: ["x"] }).map((r) => r.id)).toEqual(["a"])
  })
})

describe("toggleFilter / filterChips", () => {
  it("勾选后再取消会删掉该字段", () => {
    const on = toggleFilter({}, "status", "draft")
    expect(on).toEqual({ status: ["draft"] })
    expect(toggleFilter(on, "status", "draft")).toEqual({})
  })
  it("生成「字段：值」标签，未知值原样显示", () => {
    expect(filterChips(defs, { status: ["draft", "zzz"] }).map((c) => c.label)).toEqual(["状态：草稿", "状态：zzz"])
  })
})

describe("optionsFromRows", () => {
  it("去重并跳过空值", () => {
    expect(optionsFromRows(rows, (r) => r.type)).toEqual([
      { value: "x", label: "x" },
      { value: "y", label: "y" },
    ])
  })
})

describe("sortRows", () => {
  it("默认顺序不变", () => {
    expect(sortRows(rows, "default", acc)).toBe(rows)
  })
  it("金额高到低 / 低到高", () => {
    expect(sortRows(rows, "amount_desc", acc).map((r) => r.id)).toEqual(["a", "c", "b"])
    expect(sortRows(rows, "amount_asc", acc).map((r) => r.id)).toEqual(["b", "c", "a"])
  })
  it("最近更新在前，没有时间的排最后", () => {
    expect(sortRows(rows, "updated", acc).map((r) => r.id)).toEqual(["b", "a", "c"])
  })
  it("不修改原数组", () => {
    const copy = [...rows]
    sortRows(rows, "amount_asc", acc)
    expect(rows).toEqual(copy)
  })
})

describe("fenToYuan", () => {
  it("分 → 两位小数元，空值为空串", () => {
    expect(fenToYuan(86000)).toBe("860.00")
    expect(fenToYuan(123405)).toBe("1234.05")
    expect(fenToYuan(-150)).toBe("-1.50")
    expect(fenToYuan(0)).toBe("0.00")
    expect(fenToYuan(null)).toBe("")
  })
})

describe("toCsv", () => {
  it("带 UTF-8 BOM、CRLF，含逗号 / 引号 / 换行的单元格加引号转义", () => {
    const csv = toCsv(
      [
        { label: "名称", value: (r: { n: string; v: number | null }) => r.n },
        { label: "金额（元）", value: (r) => (r.v === null ? null : fenToYuan(r.v)) },
      ],
      [
        { n: '明理,"律所"', v: 100 },
        { n: "两行\n文字", v: null },
      ],
    )
    expect(csv.charCodeAt(0)).toBe(0xfeff)
    expect(csv.slice(1)).toBe('名称,金额（元）\r\n"明理,""律所""",1.00\r\n"两行\n文字",\r\n')
  })
})

describe("显示字段偏好", () => {
  it("parseHiddenColumns 容错", () => {
    expect(parseHiddenColumns(null)).toEqual([])
    expect(parseHiddenColumns("not json")).toEqual([])
    expect(parseHiddenColumns('{"a":1}')).toEqual([])
    expect(parseHiddenColumns('["website", 1, "owner"]')).toEqual(["website", "owner"])
  })
  it("toggleHidden 切换", () => {
    expect(toggleHidden([], "a")).toEqual(["a"])
    expect(toggleHidden(["a", "b"], "a")).toEqual(["b"])
  })
})
