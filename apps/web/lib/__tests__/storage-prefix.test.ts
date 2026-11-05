import { describe, expect, it } from "vitest"

import { AI_SESSION_PREFIX, removeByPrefix } from "@/lib/storage"

function fakeStore(init: Record<string, string>) {
  const data = new Map(Object.entries(init))
  return {
    data,
    get length() {
      return data.size
    },
    key: (i: number) => [...data.keys()][i] ?? null,
    removeItem: (k: string) => void data.delete(k),
  }
}

describe("removeByPrefix", () => {
  it("退出登录清掉所有人记住的 AI 会话，其他偏好保留（回归：退出再登录还是旧对话）", () => {
    const store = fakeStore({
      "sp.ai.u1.work": "t_1",
      "sp.ai.u1.mode": "learn",
      "sp.ai.u2.work": "t_2",
      "sp.sidebar": "open",
    })
    expect(removeByPrefix(store, AI_SESSION_PREFIX)).toBe(3)
    expect([...store.data.keys()]).toEqual(["sp.sidebar"])
  })
})
