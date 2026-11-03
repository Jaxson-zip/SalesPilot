import { afterEach, describe, expect, it, vi } from "vitest"

import { api, writeKey } from "@/lib/api"

// 回归：快速双击「创建报价单」生成了两张一样的报价
describe("相同的写请求在返回前不重复发送", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("双击只发一次，两次调用拿到同一个结果；返回后可以再发", async () => {
    let resolve: (r: Response) => void = () => {}
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((r) => {
          resolve = r
        }),
    )
    vi.stubGlobal("fetch", fetchMock)
    const a = api.post<{ id: string }>("/api/quotes", { customer_id: "c1" })
    const b = api.post<{ id: string }>("/api/quotes", { customer_id: "c1" })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolve(Response.json({ code: 0, message: "ok", data: { id: "q1" } }))
    expect(await a).toEqual({ id: "q1" })
    expect(await b).toEqual({ id: "q1" })

    fetchMock.mockImplementation(async () => Response.json({ code: 0, message: "ok", data: { id: "q2" } }))
    expect(await api.post("/api/quotes", { customer_id: "c1" })).toEqual({ id: "q2" })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("请求体不同、GET 请求不去重", () => {
    expect(writeKey("/api/x", { method: "POST", body: { a: 1 } })).not.toBe(
      writeKey("/api/x", { method: "POST", body: { a: 2 } }),
    )
    expect(writeKey("/api/x", {})).toBeNull()
  })
})
