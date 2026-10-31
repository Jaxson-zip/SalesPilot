import { describe, expect, it } from "vitest"

import { actionResultOf } from "@/lib/action-result"
import { applyAgentEvent, applyDecision, type AssistantTurn } from "@/lib/agent-reducer"
import { isWebsite, safeHref } from "@/lib/safe-url"

describe("safeHref", () => {
  it("只放行 http / https 和站内路径", () => {
    expect(safeHref("https://a.com/x")).toBe("https://a.com/x")
    expect(safeHref("/customers/1")).toBe("/customers/1")
    for (const bad of ["javascript:alert(1)", " JavaScript:alert(1)", "data:text/html,x", "//evil.com", "", null]) {
      expect(safeHref(bad)).toBeNull()
    }
  })
  it("网站地址：http(s) 或只写域名", () => {
    expect(isWebsite("https://example.com")).toBe(true)
    expect(isWebsite("example.com")).toBe(true)
    expect(isWebsite("javascript:alert(1)")).toBe(false)
    expect(isWebsite("ftp://a.com")).toBe(false)
  })
})

const turn = (): AssistantTurn => ({
  id: "a",
  role: "assistant",
  steps: [],
  text: "我来记一条跟进。",
  afterText: "",
  artifacts: [],
  interrupt: { action: "add_followup", title: "记跟进", preview: {} },
  status: "streaming",
  error: null,
  currentNode: null,
  startedAt: 0,
  endedAt: null,
})

describe("确认后的执行结果", () => {
  it("message.replace 改正确认后的续写，执行结果按 artifact 读取", () => {
    let t = applyDecision(turn(), "approve")
    t = applyAgentEvent(t, { event: "message.delta", data: { text: "请确认卡片" } })
    t = applyAgentEvent(t, { event: "message.replace", data: { text: "已完成：已记录跟进。" } })
    expect(t.afterText).toBe("已完成：已记录跟进。")
    expect(t.text).toBe("我来记一条跟进。")
    const data = { action: "add_followup", status: "done", summary: "已记录跟进", href: "/customers/1" }
    t = applyAgentEvent(t, { event: "artifact", data: { type: "action_result", data } })
    expect(actionResultOf(t.artifacts)).toEqual(data)
    expect(actionResultOf([{ id: "x", type: "action_result", data: { status: "weird" } }])).toBeNull()
  })
})
