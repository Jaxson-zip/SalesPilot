import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api"
import { errorMessage, errorMeta, isNotImplemented } from "@/lib/errors"

const err = (code: number, status: number, data?: unknown, message = "后端消息") =>
  new ApiError({ code, status, message, requestId: "req_1", data })

describe("isNotImplemented", () => {
  it("501 或 50101 视为后端开发中", () => {
    expect(isNotImplemented(err(50101, 501))).toBe(true)
    expect(isNotImplemented(err(50101, 200))).toBe(true)
    expect(isNotImplemented(err(50001, 500))).toBe(false)
    expect(isNotImplemented(new Error("x"))).toBe(false)
  })
  it("回归：路由未注册的默认 404 视为开发中，业务 40401 不算", () => {
    expect(isNotImplemented(err(40401, 404, null, "Not Found"))).toBe(true)
    expect(isNotImplemented(err(40401, 404, null, "资源不存在"))).toBe(false)
  })
})

describe("errorMessage", () => {
  it("42201 按 data.rule 给出中文说明", () => {
    expect(errorMessage(err(42201, 422, { rule: "opportunity_stage_final" }))).toContain("终态")
    expect(errorMessage(err(42201, 422, { rule: "expense_missing_invoice" }))).toContain("票据不全")
    expect(errorMessage(err(42201, 422, { rule: "unknown_rule" }))).toBe("后端消息")
  })
  it("40301 / 40901 / 501", () => {
    expect(errorMessage(err(40301, 403))).toBe("当前角色无权执行该操作")
    expect(errorMessage(err(40901, 409))).toContain("重复提交")
    expect(errorMessage(err(50101, 501))).toContain("开发中")
  })
  it("40301 按 data.rule 区分角色不允许 / 不是负责人", () => {
    expect(errorMessage(err(40301, 403, { rule: "role_forbidden" }))).toContain("管理员负责系统配置")
    expect(errorMessage(err(40301, 403, { rule: "not_owner" }))).toBe("只有负责人本人可以修改这条记录")
    expect(errorMessage(err(40301, 403, { rule: "other" }))).toBe("当前角色无权执行该操作")
    expect(errorMessage(err(40301, 403, { rule: "privacy" }))).toBe("后端消息")
  })
  it("普通 Error 与 meta", () => {
    expect(errorMessage(new Error("断网"))).toBe("断网")
    expect(errorMeta(err(40301, 403))).toBe("错误码 40301 · req_1")
    expect(errorMeta(new Error("x"))).toBeUndefined()
  })
})
