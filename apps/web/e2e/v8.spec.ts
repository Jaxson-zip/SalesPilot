import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

test.describe("审查 v8：全局搜索、审批批量处理", () => {
  test("全局搜索：点开不报错，按名称搜到客户并跳转", async ({ page }) => {
    const errors: string[] = []
    page.on("pageerror", (e) => errors.push(String(e)))
    await loginAs(page, "sales")
    await page.goto("/dashboard")
    await page.getByRole("button", { name: /搜索/ }).first().click()
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    await dialog.getByRole("combobox").fill("深圳明理")
    const hit = dialog.getByRole("option", { name: /深圳明理律师事务所/ }).first()
    await expect(hit).toBeVisible({ timeout: 15_000 })
    await hit.click()
    await expect(page).toHaveURL(/\/customers\/[^/]+$/)
    await expect(page.getByText("深圳明理律师事务所").first()).toBeVisible()
    expect(errors).toEqual([])
  })

  test("审批：筛选类型、汇总金额、全选后显示批量操作（不实际提交）", async ({ page }) => {
    await loginAs(page, "manager")
    await page.goto("/approvals")
    await expect(page.getByText(/共 \d+ 条 · 合计/)).toBeVisible()
    const types = page.getByRole("group", { name: "审批类型" })
    await types.getByRole("button", { name: /报销/ }).click()
    await expect(types.getByRole("button", { name: /报销/ })).toHaveAttribute("aria-pressed", "true")
    await page.getByRole("checkbox", { name: "全选" }).click()
    await expect(page.getByText(/已选 \d+ 条 · 合计/)).toBeVisible()
    await expect(page.getByRole("button", { name: /批量通过/ })).toBeVisible()
    await page.getByRole("checkbox", { name: "全选" }).click()
    await expect(page.getByRole("button", { name: /批量通过/ })).toHaveCount(0)
    await page.getByRole("textbox", { name: "搜索审批" }).fill("不存在的关键词xyz")
    await expect(page.getByText("没有符合条件的审批")).toBeVisible()
  })
})
