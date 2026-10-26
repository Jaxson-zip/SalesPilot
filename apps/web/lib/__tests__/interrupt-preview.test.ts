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
})
