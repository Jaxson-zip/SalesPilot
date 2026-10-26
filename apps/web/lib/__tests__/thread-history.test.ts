import { describe, expect, it } from "vitest"

import { lastUserText, messagesToTurns, toHistoryItems, type ThreadMessages } from "@/lib/thread-history"

describe("toHistoryItems", () => {
  it("updated_at → 毫秒时间戳，空标题回落为「新对话」", () => {
    const items = toHistoryItems([
      { thread_id: "t1", title: "", updated_at: "2026-10-26T08:00:00Z", opportunity_id: null },
      { thread_id: "t2", title: "出方案", updated_at: "bad", opportunity_id: null },
    ])
    expect(items[0]).toEqual({ id: "t1", title: "新对话", updatedAt: Date.parse("2026-10-26T08:00:00Z") })
    expect(items[1].updatedAt).toBe(0)
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
