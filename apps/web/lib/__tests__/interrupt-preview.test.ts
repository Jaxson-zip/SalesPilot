import { describe, expect, it } from "vitest"

import { previewRows } from "@/lib/interrupt-preview"

describe("previewRows", () => {
  it("生成报价单：隐藏内部 id，金额和毛利格式化成中文行", () => {
    const rows = previewRows({
      pack_id: "llm_deploy",
      opportunity_id: null,
      tier: "standard",
      name: "标准版",
      summary: "4× L20 48G · FP8 · vLLM",
      total_price: 37200000,
      margin_rate: 0.2944,
    })
    expect(rows).toEqual([
      ["方案", "标准版"],
      ["配置", "4× L20 48G · FP8 · vLLM"],
      ["报价", "¥372,000"],
      ["毛利", "29.4%"],
    ])
  })

  it("未登记的字段原样显示；对象字段和空值跳过", () => {
    expect(previewRows({ note: "加急", extra: { a: 1 }, empty: null })).toEqual([["note", "加急"]])
  })

  it("function calling 写操作的预览字段都有中文标签（回归：避免确认卡片出现英文字段名）", () => {
    const rows = previewRows({
      expense_type: "客户招待",
      amount: 86000,
      occurred_on: "2026-10-25",
      customer_name: "深圳明理律师事务所",
      contacts: "王律师",
      colleagues: "李薇",
      headcount: 4,
      task_title: "电话确认预算",
      due_at: "10-27 10:00",
      task_type: "电话",
      decision: "驳回",
      comment: "超标",
      lost_reason: "预算取消",
      trip: "北京 2 晚",
      target: "E-2026-005 客户招待",
    })
    for (const [label] of rows) expect(label).toMatch(/[一-龥]/)
  })
})
