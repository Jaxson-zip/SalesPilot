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
})
