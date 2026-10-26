import { describe, expect, it } from "vitest"

import { bomToCsv, safeFileName } from "@/lib/artifacts"

describe("bomToCsv", () => {
  it("金额按元、合计行在末尾、带 BOM", () => {
    const csv = bomToCsv({
      title: "标准版 · 物料清单",
      items: [{ name: "L20 服务器", quantity: "2 台", cost: 10000000, price: 12345678 }],
      totals: [{ label: "报价合计", value: "¥123,456.78" }],
    })
    expect(csv.charCodeAt(0)).toBe(0xfeff)
    expect(csv.slice(1).split("\r\n")).toEqual([
      "项目,数量,成本（元）,售价（元）",
      "L20 服务器,2 台,100000.00,123456.78",
      '报价合计,,,"¥123,456.78"',
      "",
    ])
  })
})

describe("safeFileName", () => {
  it("去掉文件名里不允许的字符", () => {
    expect(safeFileName("标准版 · 物料清单")).toBe("标准版-物料清单")
    expect(safeFileName("///")).toBe("物料清单")
  })
})
