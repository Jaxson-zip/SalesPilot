import { expect, test } from "@playwright/test"

import { Api, dragTo, loginAs, uniq } from "./helpers"

interface Customer {
  id: string
  name: string
}
interface Opportunity {
  id: string
  name: string
  stage: string
}

/** 契约 §0：无权操作的按钮不显示；管理员业务数据只读；主管不改销售的记录 */
test.describe("角色与操作权限", () => {
  test("管理员打开业务页面：顶部有只读提示，没有任何新建按钮", async ({ page }) => {
    await loginAs(page, "admin")
    for (const [path, button] of [
      ["/customers", "新建客户"],
      ["/pipeline", "新建商机"],
      ["/expenses", "新建报销"],
    ] as const) {
      await page.goto(path)
      await expect(page.getByRole("note", { name: "只读提示" })).toBeVisible()
      await expect(page.getByRole("button", { name: button })).toHaveCount(0)
    }
  })

  test("导航按角色分组：销售没有审批和系统设置，管理员有系统设置没有审批", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/dashboard")
    // 侧边栏导航（页面上还有面包屑等其他 navigation，按链接名定位更稳）
    const nav = page
    await expect(nav.getByText("工作区", { exact: true })).toBeVisible()
    await expect(nav.getByRole("link", { name: /审批/ })).toHaveCount(0)
    await expect(nav.getByRole("link", { name: /行业包配置/ })).toHaveCount(0)

    await loginAs(page, "admin")
    await page.goto("/dashboard")
    await expect(nav.getByText("系统设置", { exact: true })).toBeVisible()
    await expect(nav.getByRole("link", { name: /行业包配置/ })).toBeVisible()
    await expect(nav.getByRole("link", { name: /审批/ })).toHaveCount(0)
  })

  test("主管拖不动销售的商机卡片，打开后也没有阶段按钮", async ({ page, request }) => {
    const sales = await Api.as(request, "sales")
    const customers = await sales.call<{ items: Customer[] }>("GET", "/api/customers?view=mine&q=深圳明理&page_size=50")
    const mingli = customers.items.find((c) => c.name === "深圳明理律师事务所")
    if (!mingli) throw new Error("演示数据缺少深圳明理律师事务所")
    const opp = await sales.call<Opportunity>("POST", "/api/opportunities", {
      customer_id: mingli.id,
      name: uniq("主管越权"),
      amount: 1_000_000,
    })

    await loginAs(page, "manager")
    await page.goto("/pipeline?view=team")
    const card = page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true })
    await expect(card).toBeVisible()
    await dragTo(page, card, page.locator('[data-stage="qualified"]'))
    await expect(page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true })).toBeVisible()
    expect((await sales.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).stage).toBe("lead")

    await card.click()
    await expect(page.getByText("仅负责人可切换阶段")).toBeVisible()
    await expect(page.getByRole("button", { name: /标记为输单/ })).toHaveCount(0)
  })

  test("销售看不到登记回款按钮，主管能看到", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/contracts")
    await expect(page.getByText("C-2026-001").first()).toBeVisible()
    await expect(page.getByRole("button", { name: "登记回款" })).toHaveCount(0)

    await loginAs(page, "manager")
    await page.goto("/contracts")
    await expect(page.getByRole("button", { name: "登记回款" }).first()).toBeVisible()
  })
})
