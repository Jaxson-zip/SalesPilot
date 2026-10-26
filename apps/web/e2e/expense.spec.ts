import { expect, test } from "@playwright/test"

import { Api, loginAs, PDF, PNG, uniq } from "./helpers"

interface Expense {
  id: string
  code: string
  reason: string | null
  status: string
  attachment_count: number
}

test("新建报销：保存草稿 → 上传发票和小票 → 提交，超标进入主管审批", async ({ page, request }) => {
  await loginAs(page, "sales")
  const api = await Api.as(request, "sales")
  const reason = uniq("浏览器测试 客户晚餐")

  await page.goto("/expenses")
  await page.getByRole("button", { name: "新建报销" }).click()
  const sheet = page.getByRole("dialog", { name: "新建报销" })
  await expect(sheet).toBeVisible()

  // 第一步：填写并保存草稿（人均 ¥215，超过 ¥150 标准）
  await sheet.locator("#exp-amount").fill("860")
  await sheet.locator("#exp-headcount").fill("4")
  await sheet.getByPlaceholder(/客户：王律师/).fill("客户：王律师、陈工；我方：张晨")
  await sheet.locator("#exp-reason").fill(reason)
  await sheet.getByRole("button", { name: "保存草稿，下一步上传票据" }).click()

  // 第二步：上传票据。客户招待要求发票 + 小票，缺一项时不能提交
  const submit = page.getByRole("button", { name: "提交审批" })
  await expect(submit).toBeVisible()
  await expect(submit).toBeDisabled()

  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles({ name: "电子发票.pdf", mimeType: "application/pdf", buffer: PDF })
  await expect(page.getByText("电子发票.pdf", { exact: true })).toBeVisible()
  await expect(submit).toBeDisabled()

  await page.getByRole("combobox", { name: "票据类型" }).click()
  await page.getByRole("option", { name: "小票" }).click()
  await fileInput.setInputFiles({ name: "消费小票.png", mimeType: "image/png", buffer: PNG })
  await expect(page.getByText("消费小票.png", { exact: true })).toBeVisible()

  // 实时制度校验提示超标
  await expect(page.getByText(/超出/).first()).toBeVisible()

  await expect(submit).toBeEnabled()
  await submit.click()
  const confirm = page.getByRole("alertdialog", { name: "提交报销审批" })
  await expect(confirm).toBeVisible()
  await confirm.getByRole("button", { name: "确认提交" }).click()
  await expect(page.getByText("超出报销标准，已提交主管审批")).toBeVisible()

  const list = await api.call<{ items: Expense[] }>("GET", "/api/expenses?page_size=50")
  const saved = list.items.find((e) => e.reason === reason)
  expect(saved?.status).toBe("pending_approval")
  expect(saved?.attachment_count).toBe(2)
})

test("不支持的文件类型被拒绝，不出现在票据列表里", async ({ page, request }) => {
  await loginAs(page, "sales")
  const api = await Api.as(request, "sales")
  const draft = await api.call<Expense>("POST", "/api/expenses", {
    type: "entertainment",
    amount: 30_000,
    headcount: 2,
    occurred_on: new Date().toISOString().slice(0, 10),
    reason: uniq("浏览器测试 错误文件"),
  })

  await page.goto("/expenses")
  await page.getByText(draft.code).first().click()
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles({ name: "病毒.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") })

  await expect(page.getByText("病毒.exe")).toHaveCount(0)
  expect((await api.call<Expense>("GET", `/api/expenses/${draft.id}`)).attachment_count).toBe(0)
})
