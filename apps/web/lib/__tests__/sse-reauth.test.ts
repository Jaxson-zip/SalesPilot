import { afterEach, describe, expect, it, vi } from "vitest"

import { setUnauthorizedHandler } from "@/lib/api"
import { postSSE } from "@/lib/sse"
import type { AgentEvent } from "@/types/api"

const json = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

describe("postSSE token 失效", () => {
  afterEach(() => {
    setUnauthorizedHandler(null)
    vi.unstubAllGlobals()
  })

  it("40101 时重新登录一次再重试，和普通请求一致", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ code: 40101, message: "未登录或 token 失效", data: null }, 401))
      .mockResolvedValueOnce(
        new Response('event: done\ndata: {"thread_id":"t1"}\n\n', {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      )
    vi.stubGlobal("fetch", fetchMock)
    const relogin = vi.fn().mockResolvedValue(true)
    setUnauthorizedHandler(relogin)

    const events: AgentEvent[] = []
    await postSSE("/api/agent/chat", { thread_id: "t1", message: "你好" }, { onEvent: (e) => events.push(e) })

    expect(relogin).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(events.map((e) => e.event)).toEqual(["done"])
  })
})
