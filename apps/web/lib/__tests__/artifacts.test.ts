import { describe, expect, it } from "vitest"

import {
  isCoreQuote,
  isCoreTier,
  isCoreTiers,
  savedTierOf,
  toBomData,
  toTierCards,
  type CoreSolutionTier,
} from "@/lib/artifacts"

/** 与 core 实际推送的结构一致（services/core/app/packs/base.py SolutionTier） */
const standard: CoreSolutionTier = {
  tier: "standard",
  name: "标准版",
  summary: "4× L20 48G · FP8 · vLLM",
  items: [
    {
      sku: "srv-4l20",
      name: "GPU 服务器 4× L20 48G",
      category: "hardware",
      unit: "台",
      qty: 1,
      unit_cost: 21800000,
      unit_price: 26200000,
    },
    {
      sku: "svc-tune",
      name: "模型调优与知识库对接",
      category: "service",
      unit: "人天",
      qty: 5,
      unit_cost: 250000,
      unit_price: 600000,
    },
  ],
  total_cost: 22050000,
  total_price: 29200000,
  margin_rate: 0.2449,
  recommended: true,
}

describe("core 方案结构识别", () => {
  it("识别 core 的 SolutionTier；字段不全时不识别", () => {
    expect(isCoreTier(standard)).toBe(true)
    expect(isCoreTiers([standard])).toBe(true)
    expect(isCoreTiers([])).toBe(false)
    expect(isCoreTier({ name: "标准版", price: 1 })).toBe(false)
  })
})

describe("isCoreQuote", () => {
  it("识别 generate_quote 推送的报价单；缺少编号或金额时不识别", () => {
    const quote = { id: "b098", code: "Q-2026-002", status: "draft", total_price: 37200000, margin_rate: 0.2944 }
    expect(isCoreQuote(quote)).toBe(true)
    expect(isCoreQuote({ id: "b098", status: "draft" })).toBe(false)
  })
})

describe("toTierCards", () => {
  it("映射为方案卡片：价格为分、毛利为 0–1、保留推荐标记和档位键", () => {
    expect(toTierCards([standard])).toEqual([
      {
        name: "标准版",
        spec: "4× L20 48G · FP8 · vLLM",
        price: 29200000,
        margin: 0.2449,
        recommended: true,
        key: "standard",
      },
    ])
  })
})

describe("toBomData", () => {
  it("小计 = 单价 × 数量，数量带单位，汇总行格式化", () => {
    const bom = toBomData(standard)
    expect(bom.title).toBe("标准版 · 物料清单")
    expect(bom.items[1]).toEqual({ name: "模型调优与知识库对接", quantity: "5 人天", cost: 1250000, price: 3000000 })
    expect(bom.totals).toEqual([
      { label: "成本合计", value: "¥220,500" },
      { label: "报价合计", value: "¥292,000" },
      { label: "毛利率", value: "24.5%" },
    ])
  })
})

describe("toBomData · 软件外包成本构成", () => {
  it("cost_breakdown 和上线后 AI 调用费追加在汇总行后", () => {
    const tier = {
      ...standard,
      specs: {
        cost_breakdown: { labor: 6690000, ai_tools: 228000, third_party: 340000, services: 500000 },
        ai_monthly_cost: 10500,
      },
    }
    expect(toBomData(tier).totals.slice(3)).toEqual([
      { label: "其中人工", value: "¥66,900" },
      { label: "其中 AI 编码工具", value: "¥2,280" },
      { label: "其中第三方代采", value: "¥3,400" },
      { label: "其中部署运维", value: "¥5,000" },
      { label: "上线后 AI 调用费（客户付）", value: "¥105/月" },
    ])
    expect(toBomData(standard).totals).toHaveLength(3)
  })
})

describe("savedTierOf：确认后按实际生成的档位显示", () => {
  const economy: CoreSolutionTier = { ...standard, tier: "economy", name: "经济版", recommended: false }
  it("报价单推回前用点确认时的档位，不回到推荐档", () => {
    expect(savedTierOf([{ type: "bom", data: standard }], economy)?.tier).toBe("economy")
  })
  it("报价单推回后以后端的物料清单为准（含打开历史会话）", () => {
    const arts = [
      { type: "bom", data: economy },
      { type: "quote", data: {} },
    ]
    expect(savedTierOf(arts)?.tier).toBe("economy")
    expect(savedTierOf(arts, standard)?.tier).toBe("economy")
  })
})
