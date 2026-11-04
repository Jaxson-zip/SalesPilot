import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api"
import { sessionVerified } from "@/lib/session"
import { ErrorCode } from "@/types/api"

/** 回归：没登录或 token 失效时打开页面，通知 / 模板 / 报销三个接口先各 401 一次才跳登录页 */
describe("sessionVerified：登录核实后才渲染页面", () => {
  const err = (code: number) =>
    new ApiError({ code, message: "x", status: code === ErrorCode.UNAUTHORIZED ? 401 : 503 })

  it("没有 token、/api/me 还没回来：不渲染", () => {
    expect(sessionVerified(false, false, null)).toBe(false)
    expect(sessionVerified(true, false, null)).toBe(false)
  })
  it("/api/me 成功：渲染", () => {
    expect(sessionVerified(true, true, null)).toBe(true)
  })
  it("401（token 失效）：不渲染，等跳登录页", () => {
    expect(sessionVerified(true, false, err(ErrorCode.UNAUTHORIZED))).toBe(false)
  })
  it("网络或服务不可用：放行，由页面显示错误", () => {
    expect(sessionVerified(true, false, err(ErrorCode.NETWORK))).toBe(true)
  })
})
