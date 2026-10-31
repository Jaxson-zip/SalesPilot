import { describe, expect, it } from "vitest"

import { feedbackSlots } from "@/lib/agent-feedback"
import type { ChatTurn } from "@/lib/agent-reducer"

const u = (id: string, text = id): ChatTurn => ({ id, role: "user", text })
const a = (id: string) => ({ id, role: "assistant" }) as unknown as ChatTurn
const idx = (turns: ChatTurn[]) => Object.fromEntries([...feedbackSlots(turns)].map(([k, v]) => [k, v.index]))

describe("点赞点踩的序号：刷新前后对得上", () => {
  it("一问一答按轮次编号，带上对应的提问", () => {
    const m = feedbackSlots([u("u1", "提成怎么算"), a("a1"), u("u2"), a("a2")])
    expect(m.get("a1")).toEqual({ index: 0, question: "提成怎么算" })
    expect(m.get("a2")?.index).toBe(1)
  })

  it("重新生成：界面上 [问, 答, 重答]，历史里是 [问, 答, 问, 重答]，重答都是第 1 轮", () => {
    expect(idx([u("u1"), a("a1"), a("a1b")])).toEqual({ a1: 0, a1b: 1 })
    expect(idx([u("u1"), a("a1"), u("u1again"), a("a1b")])).toEqual({ a1: 0, a1b: 1 })
  })

  it("出错没有回复的一轮：历史里两条问挨着，后面的序号不受影响", () => {
    // 界面上出错那轮有一条失败的 AI 回复，历史里没有
    expect(idx([u("u1"), a("err"), u("u2"), a("a2")]).a2).toBe(1)
    expect(idx([u("u1"), u("u2"), a("a2")]).a2).toBe(1)
  })
})
