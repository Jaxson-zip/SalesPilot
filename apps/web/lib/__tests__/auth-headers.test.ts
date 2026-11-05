import { describe, expect, it } from "vitest"

import { buildHeaders, CSRF_HEADER } from "@/lib/api"

/** 登录态改放 HttpOnly Cookie：请求不再带 Authorization，写请求靠 X-Requested-With 过 CSRF 校验 */
describe("buildHeaders：Cookie 登录态", () => {
  it("带 CSRF 请求头和请求 ID，不带 Authorization", () => {
    const h = buildHeaders(undefined, "req_test")
    expect(h.get(CSRF_HEADER)).toBe("XMLHttpRequest")
    expect(h.get("X-Request-ID")).toBe("req_test")
    expect(h.has("Authorization")).toBe(false)
  })
  it("保留调用方传入的请求头", () => {
    const h = buildHeaders({ Accept: "text/event-stream" })
    expect(h.get("Accept")).toBe("text/event-stream")
    expect(h.get(CSRF_HEADER)).toBe("XMLHttpRequest")
  })
})
