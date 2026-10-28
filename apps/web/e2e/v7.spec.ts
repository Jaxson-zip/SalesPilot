import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const ASK = "给明理律所出一份 Qwen3-32B 私有化方案，50 人并发，做合同审查，预算 40 万以内"

test.describe("v7：AI 生成中切页面 / 刷新不丢", () => {
  test("生成到一半切去客户页，侧栏提示生成中；回来会话还在并接着完成", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/ai")
    await page.getByRole("textbox").first().fill(ASK)
    await page.keyboard.press("Enter")
    await expect(page).toHaveURL(/\/ai\?t=/)
    const url = page.url()

    await page.getByRole("link", { name: "客户", exact: true }).click()
    await expect(page).toHaveURL(/\/customers/)
    await page.getByRole("link", { name: "AI 方案工作台" }).first().click()
    await expect(page).toHaveURL(url) // 回来时会话 id 补回地址
    await expect(page.getByText(ASK).last()).toBeVisible()
    await expect(page.getByRole("button", { name: "确认执行" })).toBeVisible({ timeout: 90_000 })
  })

  test("生成中刷新页面：重新接上这一轮，最后照样出现确认框", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/ai")
    await page.getByRole("textbox").first().fill(ASK)
    await page.keyboard.press("Enter")
    await expect(page).toHaveURL(/\/ai\?t=/)
    await page.reload()
    await expect(page.getByText(ASK).last()).toBeVisible()
    await expect(page.getByRole("button", { name: "确认执行" })).toBeVisible({ timeout: 90_000 })
    await expect(page.getByRole("button", { name: "确认执行" })).toHaveCount(1) // 这一轮没有重复出现
  })
})

test.describe("v7：工作台动态与业务规则布局", () => {
  test("团队动态只显示最近 6 条，其余在「查看全部」面板里", async ({ page }) => {
    await loginAs(page, "manager")
    await page.goto("/dashboard")
    const feed = page.getByRole("list", { name: "团队动态" })
    await expect(feed.getByRole("listitem").first()).toBeVisible()
    expect(await feed.getByRole("listitem").count()).toBeLessThanOrEqual(6)
    await page.getByRole("button", { name: "查看全部" }).click()
    const all = page.getByRole("dialog").getByRole("list", { name: "全部团队动态" })
    await expect(all.getByRole("listitem").nth(6)).toBeVisible()
  })

  test("业务规则按分组切换，一次只显示一组", async ({ page }) => {
    await loginAs(page, "admin")
    await page.goto("/settings/rules")
    await expect(page.getByRole("region", { name: "报价与审批" })).toBeVisible()
    await page.getByRole("navigation", { name: "规则分组" }).getByRole("button", { name: /回款/ }).click()
    const group = page.getByRole("region", { name: "回款" })
    await expect(group).toContainText("标准回款计划")
    await expect(group).toContainText("签订后 60 天")
    await expect(page.getByRole("region", { name: "报价与审批" })).toHaveCount(0)
  })
})
