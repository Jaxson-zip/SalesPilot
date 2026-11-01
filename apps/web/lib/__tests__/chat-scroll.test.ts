import { describe, expect, it } from "vitest"

import { nextStick } from "@/lib/chat-scroll"

describe("nextStick", () => {
  const view = { scrollHeight: 3000, clientHeight: 500 }

  it("回归：程序滚到底后内容突然变高，不算用户翻看（原来确认需求后三档报价出来了视图却不动）", () => {
    expect(nextStick(true, { ...view, lastTop: 700, top: 700 })).toBe(true)
  })

  it("用户往上翻停止跟随，翻回底部附近恢复", () => {
    expect(nextStick(true, { ...view, lastTop: 2500, top: 1800 })).toBe(false)
    expect(nextStick(false, { ...view, lastTop: 1800, top: 2000 })).toBe(false)
    expect(nextStick(false, { ...view, lastTop: 2000, top: 2450 })).toBe(true)
  })
})
