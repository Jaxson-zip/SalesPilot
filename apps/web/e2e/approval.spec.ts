import { expect, test } from "@playwright/test"

import { Api, loginAs, PDF, PNG, uniq } from "./helpers"

interface Expense {
  id: string
  code: string
  status: string
}

/** 销售通过接口提交一张超标报销（人均 ¥215），返回报销单 */
async function overLimitExpense(api: Api): Promise<Expense> {
  const draft = await api.call<Expense>("POST", "/api/expenses", {
    type: "entertainment",
    amount: 86_000,
    headcount: 4,
    occurred_on: new Date().toISOString().slice(0, 10),
    reason: uniq("审批测试 方案沟通晚餐"),
  })
  await api.upload(draft.id, "invoice", "invoice.pdf", "application/pdf", PDF)
  await api.upload(draft.id, "receipt", "receipt.png", "image/png", PNG)
  const submitted = await api.call<Expense>("POST", `/api/expenses/${draft.id}/submit`)
  expect(submitted.status).toBe("pending_approval")
  return submitted
}

test.describe("审批中心（主管）", () => {
  test("通过超标报销：从待处理移到已处理，报销单变为已通过", async ({ page, request }) => {
    const sales = await Api.as(request, "sales")
    const expense = await overLimitExpense(sales)

    await loginAs(page, "manager")
    await page.goto("/approvals")
    const row = page
      .locator("article, li, div")
      .filter({ hasText: expense.code })
      .filter({
        has: page.getByRole("button", { name: "通过" }),
      })
    await expect(row.last()).toBeVisible()
    // 附件和制度校验原因都能看到
    await expect(row.last()).toContainText("invoice.pdf")
    await expect(row.last()).toContainText("超出")

    await row.last().getByRole("button", { name: "通过" }).click()
    const confirm = page.getByRole("alertdialog", { name: "通过审批" })
    await expect(confirm).toBeVisible()
    await confirm.getByRole("button", { name: "确认通过" }).click()
    await expect(page.getByText(expense.code)).toHaveCount(0)
    await expect
      .poll(async () => (await sales.call<Expense>("GET", `/api/expenses/${expense.id}`)).status)
      .toBe("approved")

    await page.getByRole("tab", { name: /已处理/ }).click()
    await expect(page.getByText(expense.code).first()).toBeVisible()
  })

  test("驳回时可以填写意见，报销单变为已驳回", async ({ page, request }) => {
    const sales = await Api.as(request, "sales")
    const expense = await overLimitExpense(sales)

    await loginAs(page, "manager")
    await page.goto("/approvals")
    const row = page
      .locator("article, li, div")
      .filter({ hasText: expense.code })
      .filter({
        has: page.getByRole("button", { name: "驳回" }),
      })
    await row.last().getByRole("button", { name: "驳回" }).click()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    await dialog.getByRole("textbox").fill("人均超标较多，请拆分或补充说明")
    await dialog.getByRole("button", { name: /驳回/ }).click()

    await expect(dialog).toBeHidden()
    await expect
      .poll(async () => (await sales.call<Expense>("GET", `/api/expenses/${expense.id}`)).status)
      .toBe("rejected")
  })

  test("销售打开审批中心看到锁定提示，不显示审批操作", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/approvals")
    await expect(page.getByRole("button", { name: "通过" })).toHaveCount(0)
    await expect(page.getByText(/主管/).first()).toBeVisible()
  })
})
