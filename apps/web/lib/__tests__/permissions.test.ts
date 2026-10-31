import { describe, expect, it } from "vitest"

import {
  canApprove,
  canConfigurePacks,
  canCreateBusiness,
  canEditRecord,
  canRegisterPayment,
  canUseAiApprove,
  canUseAiQuery,
  canUseAiWrite,
  canWriteFollowup,
  isOwner,
  isReadOnlyRole,
} from "@/lib/permissions"
import type { Role } from "@/types/api"

/** 契约 §0 权限矩阵逐行覆盖 */
const ME = "u_me"
const OTHER = "u_other"
const roles: Role[] = ["sales", "manager", "admin"]
const by = (fn: (r: Role) => boolean) => Object.fromEntries(roles.map((r) => [r, fn(r)]))

describe("permissions · 契约 §0 矩阵", () => {
  it("查看：管理员是只读角色", () => {
    expect(by(isReadOnlyRole)).toEqual({ sales: false, manager: false, admin: true })
  })

  it("新建客户、商机、报销：销售 ✅ 主管 ✅ 管理员 ❌", () => {
    expect(by(canCreateBusiness)).toEqual({ sales: true, manager: true, admin: false })
  })

  it("写跟进：销售 ✅ 主管 ✅ 管理员 ❌", () => {
    expect(by(canWriteFollowup)).toEqual({ sales: true, manager: true, admin: false })
  })

  it("修改商机 / 切换阶段 / 拖拽、报价操作、报销票据与提交：仅本人的", () => {
    expect(by((r) => canEditRecord(r, ME, ME))).toEqual({ sales: true, manager: true, admin: false })
    expect(by((r) => canEditRecord(r, OTHER, ME))).toEqual({ sales: false, manager: false, admin: false })
  })

  it("负责人或当前用户未知时不显示（宁可隐藏）", () => {
    expect(canEditRecord("sales", ME, null)).toBe(false)
    expect(canEditRecord("sales", undefined, ME)).toBe(false)
    expect(isOwner(null, null)).toBe(false)
    expect(isOwner(ME, ME)).toBe(true)
  })

  it("审批报价和报销：仅主管", () => {
    expect(by(canApprove)).toEqual({ sales: false, manager: true, admin: false })
  })

  it("登记回款：仅主管，且合同在回款中", () => {
    expect(by((r) => canRegisterPayment(r))).toEqual({ sales: false, manager: true, admin: false })
    expect(canRegisterPayment("manager", { status: "active" })).toBe(true)
    expect(canRegisterPayment("manager", { status: "paid" })).toBe(false)
    expect(canRegisterPayment("admin", { status: "active" })).toBe(false)
  })

  it("AI 查询类工具：所有角色", () => {
    expect(by(canUseAiQuery)).toEqual({ sales: true, manager: true, admin: true })
  })

  it("AI 写操作工具：销售 ✅ 主管 ✅ 管理员 ❌", () => {
    expect(by(canUseAiWrite)).toEqual({ sales: true, manager: true, admin: false })
  })

  it("AI 审批工具：仅主管", () => {
    expect(by(canUseAiApprove)).toEqual({ sales: false, manager: true, admin: false })
  })

  it("行业包配置、产品线映射：仅管理员", () => {
    expect(by(canConfigurePacks)).toEqual({ sales: false, manager: false, admin: true })
  })

  it("个人模式下主管可以改系统配置，销售不行", () => {
    expect(canConfigurePacks("manager")).toBe(false)
    expect(canConfigurePacks("manager", true)).toBe(true)
    expect(canConfigurePacks("sales", true)).toBe(false)
    expect(canConfigurePacks("admin")).toBe(true)
  })
})
