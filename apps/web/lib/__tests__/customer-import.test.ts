import { describe, expect, it } from "vitest"

import { fileProblem, importTemplate, previewSummary, rowsToShow, type ImportResult } from "@/lib/customer-import"

const result: ImportResult = {
  total: 4,
  ok: 2,
  skipped: 2,
  created: false,
  columns: ["name"],
  ignored_columns: [],
  rows: [
    { line: 2, name: "甲", owner_name: "张晨", status: "ok", message: null, warnings: [] },
    { line: 3, name: "乙", owner_name: "张晨", status: "ok", message: null, warnings: ["名称相似：乙方"] },
    { line: 4, name: "丙", owner_name: "张晨", status: "duplicate", message: "客户已存在：丙", warnings: [] },
    { line: 5, name: "", owner_name: "张晨", status: "error", message: "客户名称为空", warnings: [] },
  ],
}

describe("客户导入", () => {
  it("模板带 BOM；主管多一列负责人", () => {
    const sales = importTemplate(false)
    expect(sales.startsWith("\uFEFF客户名称*")).toBe(true)
    expect(sales).not.toContain("负责人")
    expect(importTemplate(true).split("\r\n")[0].endsWith(",负责人")).toBe(true)
  })

  it("选文件时拦掉格式和大小不对的", () => {
    expect(fileProblem({ name: "a.xls", size: 10 })).toBe("只支持 .csv 和 .xlsx 文件")
    expect(fileProblem({ name: "a.CSV", size: 3 * 1024 * 1024 })).toContain("2MB")
    expect(fileProblem({ name: "客户.xlsx", size: 10 })).toBeNull()
  })

  it("预览汇总和只列有问题 / 有提示的行", () => {
    expect(previewSummary(result)).toBe("共 4 行：可导入 2 行，跳过 2 行（重复 1、有错误 1）")
    expect(previewSummary({ ...result, ok: 4, skipped: 0, rows: [] })).toBe("共 4 行：可导入 4 行")
    expect(rowsToShow(result).map((r) => r.line)).toEqual([3, 4, 5])
  })
})
