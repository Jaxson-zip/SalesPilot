import { describe, expect, it } from "vitest"

import {
  addModule,
  canConfirm,
  confirmedRequirement,
  isRequirementCard,
  removeModule,
  togglePlatform,
  updateModule,
  type Requirement,
} from "@/lib/requirement-card"

const req: Requirement = {
  platforms: ["mini_program", "admin"],
  modules: [
    { key: "account", name: "会员登录", complexity: "medium", must: true, source: "mentioned" },
    { key: "rbac", name: "多门店权限", complexity: "medium", must: true, source: "inferred" },
  ],
  questions: ["有几种角色？"],
}

describe("requirement-card", () => {
  it("类型守卫：缺价格区间或模块结构不对时不渲染卡片", () => {
    expect(isRequirementCard({ requirement: req, price_low: 1, price_high: 2, inferred: 1, questions: [] })).toBe(true)
    expect(isRequirementCard({ requirement: req })).toBe(false)
    expect(isRequirementCard({ requirement: { platforms: [], modules: [{}] }, price_low: 1, price_high: 2 })).toBe(
      false,
    )
  })

  it("切换端、改复杂度和批次、删除模块都不改原对象", () => {
    const a = togglePlatform(req, "admin")
    expect(a.platforms).toEqual(["mini_program"])
    expect(togglePlatform(a, "app").platforms).toEqual(["mini_program", "app"])
    const b = updateModule(req, 1, { complexity: "complex", must: false })
    expect(b.modules[1]).toMatchObject({ complexity: "complex", must: false })
    expect(removeModule(req, 0).modules.map((m) => m.name)).toEqual(["多门店权限"])
    expect(req.modules).toHaveLength(2)
  })

  it("补充功能按自定义模块，重名和空白不加", () => {
    const r = addModule(req, " 会员积分 ")
    expect(r.modules.at(-1)).toEqual({
      key: "custom",
      name: "会员积分",
      complexity: "medium",
      must: true,
      source: "mentioned",
    })
    expect(addModule(r, "会员积分").modules).toHaveLength(3)
    expect(addModule(req, "  ").modules).toHaveLength(2)
  })

  it("确认时全部算客户确认、清掉问题；没有端或模块不能确认", () => {
    const c = confirmedRequirement(req) as Requirement
    expect(c.modules.every((m) => m.source === "mentioned")).toBe(true)
    expect(c.questions).toEqual([])
    expect(canConfirm(req)).toBe(true)
    expect(canConfirm({ ...req, platforms: [] })).toBe(false)
    expect(canConfirm({ ...req, modules: [] })).toBe(false)
  })
})
