import { describe, expect, it } from "vitest"

import { knowledgeMissingHint, knowledgeSummary, knowledgeSummaryText } from "@/lib/knowledge"

describe("knowledgeSummary", () => {
  it("回归：顶部统计和每份文档的入库状态同一口径（原来写「3 份参与检索」，下面三份都是未入库）", () => {
    const docs = [{ chunks: 0 }, { chunks: 0 }, { chunks: 0 }, { indexed: false, chunks: null }]
    const s = knowledgeSummary(docs)
    expect(s).toEqual({ total: 4, indexable: 3, ingested: 0 })
    expect(knowledgeSummaryText(s, true)).toBe("4 份文档 · 3 份可检索，已入库 0 份")
    expect(knowledgeMissingHint(s, true)).toContain("3 份文档还没入库")
  })

  it("都入库了不提示；统计不到切块数时不说已入库多少", () => {
    const s = knowledgeSummary([{ chunks: 5 }, { chunks: 2 }])
    expect(knowledgeMissingHint(s, true)).toBeNull()
    expect(knowledgeSummaryText(s, false)).toBe("2 份文档 · 2 份可检索")
    expect(knowledgeMissingHint(s, false)).toBeNull()
  })
})
