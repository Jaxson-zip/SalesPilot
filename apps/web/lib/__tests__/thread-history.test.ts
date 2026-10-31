import { describe, expect, it } from "vitest"

import {
  aiPrefillHref,
  opportunityPrompt,
  lastUserText,
  messagesToTurns,
  solutionPrompt,
  toHistoryItems,
  type ThreadMessages,
} from "@/lib/thread-history"

describe("toHistoryItems", () => {
  it("updated_at → 毫秒时间戳，空标题回落为「新对话」", () => {
    const items = toHistoryItems([
      { thread_id: "t1", title: "", updated_at: "2026-10-26T08:00:00Z", opportunity_id: null },
      { thread_id: "t2", title: "出方案", updated_at: "bad", opportunity_id: null, mode: "learn" },
    ])
    expect(items[0]).toEqual({
      id: "t1",
      title: "新对话",
      updatedAt: Date.parse("2026-10-26T08:00:00Z"),
      running: false,
      learn: false,
    })
    expect(items[1].updatedAt).toBe(0)
    expect(items[1].learn).toBe(true)
  })
})

describe("messagesToTurns", () => {
  const data: ThreadMessages = {
    thread_id: "t1",
    messages: [
      { role: "user", text: "给明理律所出方案" },
      {
        role: "assistant",
        text: "方案如下",
        artifacts: [{ type: "solution_tiers", data: [] }],
        created_at: "2026-10-26T08:00:00Z",
      },
    ],
  }

  it("还原用户消息、AI 文字和卡片，状态为已完成", () => {
    const turns = messagesToTurns(data)
    expect(turns).toHaveLength(2)
    expect(turns[0]).toMatchObject({ role: "user", text: "给明理律所出方案" })
    const ai = turns[1]
    if (ai.role !== "assistant") throw new Error("expected assistant")
    expect(ai.status).toBe("done")
    expect(ai.text).toBe("方案如下")
    expect(ai.artifacts.map((a) => a.type)).toEqual(["solution_tiers"])
    expect(ai.interrupt).toBeNull()
  })

  it("有待确认操作时挂到最后一条 AI 回复上", () => {
    const turns = messagesToTurns({ ...data, pending: { action: "generate_quote", preview: { 客户: "明理律所" } } })
    const ai = turns[1]
    if (ai.role !== "assistant") throw new Error("expected assistant")
    expect(ai.interrupt).toMatchObject({ action: "generate_quote", preview: { 客户: "明理律所" } })
    expect(ai.interrupt?.decision).toBeUndefined()
  })

  it("pending 格式不对时忽略", () => {
    const turns = messagesToTurns({ ...data, pending: { preview: 1 } })
    const ai = turns[1]
    if (ai.role !== "assistant") throw new Error("expected assistant")
    expect(ai.interrupt).toBeNull()
  })

  it("lastUserText 取最后一条用户消息", () => {
    expect(lastUserText(messagesToTurns(data))).toBe("给明理律所出方案")
    expect(lastUserText([])).toBeNull()
  })
})

describe("商机出方案：直接发给 AI 的内容", () => {
  it("商机、预计金额、最近跟进（这一个商机的），链接带 send=1", () => {
    const text = opportunityPrompt({
      customer: "明理律所",
      name: "合同审查",
      amount: 40_000_000,
      followups: [
        { content: "要私有化部署，50 人用", occurred_at: "2026-10-24T10:00:00Z", created_at: "2026-10-24T10:00:00Z" },
        { content: "  ", occurred_at: null, created_at: "2026-10-20T10:00:00Z" },
      ],
    })
    expect(text).toBe(
      "给「明理律所」的「合同审查」商机出一份方案。\n商机预计金额约 ¥400,000。\n最近的跟进记录：\n- 10-24 要私有化部署，50 人用",
    )
    expect(opportunityPrompt({ customer: "A", name: "B" })).toContain("缺什么信息请直接问我")
    const url = new URL(aiPrefillHref(text, "o1", true), "http://x")
    expect(url.searchParams.get("send")).toBe("1")
    expect(url.searchParams.get("prompt")).toBe(text)
  })
})

describe("出方案带上下文", () => {
  it("预填客户和商机，链接带 prompt 和商机 id", () => {
    expect(solutionPrompt("深职大")).toBe("给「深职大」出一份方案：")
    expect(solutionPrompt("深职大", "AI 客服")).toBe("给「深职大」的「AI 客服」商机出一份方案：")
    const url = new URL(aiPrefillHref("给「深职大」出一份方案：", "o1"), "http://x")
    expect(url.pathname).toBe("/ai")
    expect(url.searchParams.get("prompt")).toBe("给「深职大」出一份方案：")
    expect(url.searchParams.get("opp")).toBe("o1")
    expect(new URL(aiPrefillHref("x"), "http://x").searchParams.has("opp")).toBe(false)
  })
})
