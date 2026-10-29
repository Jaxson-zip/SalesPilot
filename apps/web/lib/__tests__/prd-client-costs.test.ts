import { describe, expect, it } from "vitest"

import { toBomData, type CoreSolutionTier } from "@/lib/artifacts"
import { costAmount, costSummary, isClientCosts, type ClientCost } from "@/lib/client-costs"
import { prdFileName } from "@/lib/prd"
import { formatSetting, parseInputText, toInputText } from "@/lib/settings"

const costs: ClientCost[] = [
  { name: "云服务器与数据库", amount: 300_000, period: "year" },
  { name: "域名与 SSL 证书", amount: 10_000, period: "year" },
  { name: "大模型调用费（AI 功能）", amount: 45_000, period: "month" },
]

describe("客户自付费用", () => {
  it("按年 / 按月分别合计", () => {
    expect(costSummary(costs)).toBe("¥3,100/年 + ¥450/月")
    expect(costSummary(costs.slice(0, 1))).toBe("¥3,000/年")
    expect(costAmount(costs[2])).toBe("¥450/月")
    expect(isClientCosts(costs)).toBe(true)
    expect(isClientCosts([{ name: 1 }])).toBe(false)
  })

  it("物料清单：带出客户自付费用，成本构成跳过 0，AI 调用费不再放进合计", () => {
    const tier: CoreSolutionTier = {
      tier: "standard",
      name: "标准版",
      summary: "",
      items: [],
      total_cost: 100,
      total_price: 200,
      margin_rate: 0.5,
      specs: {
        cost_breakdown: { labor: 80, ai_tools: 20, third_party: 0, services: 0 },
        ai_monthly_cost: 45_000,
        client_costs: costs,
      },
    }
    const bom = toBomData(tier)
    expect(bom.client_costs).toEqual(costs)
    const labels = bom.totals.map((t) => t.label)
    expect(labels).toContain("其中人工")
    expect(labels).not.toContain("其中第三方代采")
    expect(labels).not.toContain("上线后 AI 调用费（客户付）")
  })
})

describe("prdFileName", () => {
  it("去掉文件名不允许的字符", () => {
    expect(prdFileName("门店 预约/小程序")).toBe("门店-预约-小程序-PRD规格书.md")
    expect(prdFileName("  ")).toBe("项目-PRD规格书.md")
  })
})

describe("开关类型的配置", () => {
  const field = { kind: "bool" as const, min: null, max: null, label: "第三方费用计入报价" }
  it("显示、输入框文字与解析", () => {
    expect(formatSetting("bool", true)).toBe("开")
    expect(formatSetting("bool", false)).toBe("关")
    expect(toInputText("bool", false)).toBe("false")
    expect(parseInputText(field, "true")).toEqual({ ok: true, value: true })
    expect(parseInputText(field, "false")).toEqual({ ok: true, value: false })
  })
})
