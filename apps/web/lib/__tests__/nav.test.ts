import { describe, expect, it } from "vitest"

import { contractsLabel, isBusinessPath, isForbiddenPath, navGroupsFor, navItemsFor } from "@/lib/nav"
import type { Role } from "@/types/api"

const labels = (role: Role) => navGroupsFor(role).map((g) => g.label ?? "")
const hrefs = (role: Role) => navItemsFor(role).map((i) => i.href)

describe("导航按角色分组（契约 §0）", () => {
  it("销售：工作区", () => {
    expect(labels("sales")).toEqual(["", "工作区"])
    expect(hrefs("sales")).not.toContain("/approvals")
    expect(hrefs("sales")).not.toContain("/settings/packs")
  })

  it("主管：工作区 + 团队管理（审批、合同与回款）", () => {
    expect(labels("manager")).toEqual(["", "工作区", "团队管理"])
    const team = navGroupsFor("manager")[2].items.map((i) => i.label)
    expect(team).toEqual(["审批", "合同与回款", "操作日志"])
  })

  it("管理员：业务总览（只读）+ 系统设置", () => {
    expect(labels("admin")).toEqual(["", "业务总览（只读）", "系统设置"])
    expect(navGroupsFor("admin")[2].items.map((i) => i.href)).toEqual([
      "/settings/rules",
      "/settings/packs",
      "/battlecards",
      "/settings/integrations",
      "/settings/audit",
    ])
    expect(hrefs("admin")).not.toContain("/approvals")
  })

  it("同一页面不会在两个分组里重复出现", () => {
    for (const role of ["sales", "manager", "admin"] as Role[]) {
      const list = hrefs(role)
      expect(new Set(list).size).toBe(list.length)
    }
  })

  it("合同页名称随角色变化", () => {
    expect(contractsLabel("manager")).toBe("合同与回款")
    expect(contractsLabel("sales")).toBe("合同与提成")
  })

  it("切换角色后无权页面需要跳回", () => {
    expect(isForbiddenPath("/approvals", "sales")).toBe(true)
    expect(isForbiddenPath("/approvals", "admin")).toBe(true)
    expect(isForbiddenPath("/approvals", "manager")).toBe(false)
    expect(isForbiddenPath("/settings/packs", "manager")).toBe(true)
    expect(isForbiddenPath("/settings/audit", "sales")).toBe(true)
    expect(isForbiddenPath("/settings/audit", "manager")).toBe(false)
    expect(isForbiddenPath("/settings/integrations", "manager")).toBe(true)
    expect(isForbiddenPath("/quotes/q1", "admin")).toBe(false)
    for (const role of ["sales", "manager", "admin"] as Role[]) {
      expect(isForbiddenPath("/battlecards", role)).toBe(false)
      expect(isForbiddenPath("/reports", role)).toBe(false)
    }
  })

  it("业务页面识别（管理员只读提示）", () => {
    expect(isBusinessPath("/customers/c1")).toBe(true)
    expect(isBusinessPath("/ai")).toBe(true)
    expect(isBusinessPath("/settings/packs")).toBe(false)
    expect(isBusinessPath("/approvals")).toBe(false)
  })
})
