import { describe, expect, it } from "vitest"

import { handoverSummary, transferConfirm } from "@/lib/confirm-texts"
import { INDUSTRY_OPTIONS, SIZE_OPTIONS } from "@/lib/customer"
import { applyFilters } from "@/lib/list-view"
import { expectedCloseText, opportunityFilters, STALE_FILTER } from "@/lib/pipeline"
import type { OpportunityItem } from "@/types/api"

const opp = (over: Partial<OpportunityItem>): OpportunityItem => ({
  id: "o",
  name: "商机",
  customer: { id: "c", name: "客户" },
  stage: "proposal",
  amount: 100,
  win_rate: 50,
  expected_close_date: null,
  product_line: null,
  owner: { id: "u", name: "张晨" },
  updated_at: "2026-10-26T00:00:00Z",
  ...over,
})

describe("看板卡片预计成交日（U8）", () => {
  const now = new Date(2026, 9, 26)
  it("同年显示「预计 MM-DD」，跨年带年份", () => {
    expect(expectedCloseText("2026-11-30", now)).toBe("预计 11-30")
    expect(expectedCloseText("2027-01-15", now)).toBe("预计 2027-01-15")
    expect(expectedCloseText(null, now)).toBe("预计成交日未设置")
  })
})

describe("只看停滞（v3 §13）", () => {
  it("筛选里包含「只看停滞」，按后端 stale 过滤", () => {
    const rows = [opp({ id: "a", stale: true, idle_days: 20 }), opp({ id: "b", stale: false }), opp({ id: "c" })]
    expect(opportunityFilters(rows).some((f) => f.id === STALE_FILTER.id)).toBe(true)
    expect(applyFilters(rows, [STALE_FILTER], { stale: ["stale"] }).map((o) => o.id)).toEqual(["a"])
  })
})

describe("新建客户字典（U7）", () => {
  it("行业、规模为固定选项", () => {
    expect(INDUSTRY_OPTIONS).toContain("法律服务")
    expect(INDUSTRY_OPTIONS[INDUSTRY_OPTIONS.length - 1]).toBe("其他")
    expect(SIZE_OPTIONS).toEqual(["1–49 人", "50–199 人", "200–499 人", "500–999 人", "1000 人以上"])
  })
})

describe("转移负责人确认文案（v3 §16）", () => {
  it("写明数量、范围和新负责人", () => {
    const c = transferConfirm(3, "李娜")
    expect(c.title).toBe("转移负责人")
    expect(c.confirmLabel).toBe("确认转移")
    expect(c.description).toContain("3 个客户及其未结束的商机")
    expect(c.description).toContain("「李娜」")
  })
  it("未选择新负责人时提示选择", () => {
    expect(transferConfirm(2, null).description).toContain("请选择本团队的新负责人")
  })
})

describe("按人交接", () => {
  it("只列出有数量的项", () => {
    expect(handoverSummary({ customers: 3, opportunities: 2, tasks: 0, quotes: 1, contracts: 1 })).toBe(
      "3 个客户、2 个进行中的商机、1 份未成交的报价、1 份回款中的合同",
    )
    expect(handoverSummary({ customers: 0, opportunities: 0, tasks: 0, quotes: 0, contracts: 0 })).toBe("")
  })
})
