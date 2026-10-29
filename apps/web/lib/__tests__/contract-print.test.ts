import { describe, expect, it } from "vitest"

import { contractDocTitle, planGap, planRatio, prdForPrint, sowScope } from "@/lib/contract-print"

describe("合同要素确认单", () => {
  it("文件名带合同编号和客户", () => {
    expect(contractDocTitle({ code: "C-2026-001", customer: { id: "c", name: "明理律所" } })).toBe(
      "合同要素确认单-C-2026-001-明理律所",
    )
    expect(contractDocTitle({ code: "C-2026-002", customer: null })).toBe("合同要素确认单-C-2026-002")
  })

  it("每期比例与合计核对", () => {
    expect(planRatio(30_000, 100_000)).toBe("30%")
    expect(planRatio(1, 0)).toBe("—")
    expect(planGap([{ amount: 30_000 }, { amount: 60_000 }, { amount: 10_000 }], 100_000)).toBe(0)
    expect(planGap([{ amount: 30_000 }], 100_000)).toBe(70_000)
  })
})

describe("合同附件：需求范围说明书", () => {
  it("没有 PRD 时按需求清单列出交付端和首期 / 二期", () => {
    const s = sowScope({
      platforms: ["mini_program", "admin"],
      modules: [{ name: "在线预约" }, { name: "数据报表", must: false }],
    })
    expect(s.platforms).toBe("微信小程序、管理后台")
    expect(s.modules).toEqual([
      { name: "在线预约", phase: "首期" },
      { name: "数据报表", phase: "二期" },
    ])
  })

  it("附进合同的 PRD 去掉草案提示", () => {
    const md = `# 标题

> AI 生成的草案，需要确认。

## 1 背景
> 引用保留`
    expect(prdForPrint(md)).toBe(`# 标题

## 1 背景
> 引用保留`)
  })
})
