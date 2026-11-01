import { ChartNoAxesColumn, Receipt, Sparkles } from "lucide-react"
import { describe, expect, it } from "vitest"

import { promptCardsFrom } from "@/components/agent/PromptCards"

describe("promptCardsFrom", () => {
  it("按标题关键词配图标，未匹配用默认图标", () => {
    const cards = promptCardsFrom([
      { title: "对话报销", prompt: "a" },
      { title: "团队漏斗", prompt: "b" },
      { title: "随便问问", prompt: "c" },
    ])
    expect(cards.map((c) => c.icon)).toEqual([Receipt, ChartNoAxesColumn, Sparkles])
    expect(cards[0]).toMatchObject({ title: "对话报销", prompt: "a" })
  })

  it("出方案卡片换成当前行业包的例句；没有例句时用模板兜底（回归：选软件外包却示例大模型部署）", () => {
    const templates = [
      { title: "出方案报价", prompt: "Qwen3-32B 私有化方案", pack_example: true },
      { title: "对话报销", prompt: "报销 860" },
    ]
    const cards = promptCardsFrom(templates, "蛋糕预订小程序")
    expect(cards.map((c) => c.prompt)).toEqual(["蛋糕预订小程序", "报销 860"])
    expect(promptCardsFrom(templates)[0].prompt).toBe("Qwen3-32B 私有化方案")
  })
})
