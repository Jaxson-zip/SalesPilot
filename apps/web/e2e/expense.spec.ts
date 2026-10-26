import { expect, test } from "@playwright/test"

import { Api, entertainmentDraft, loginAs, PDF, PNG, uniq } from "./helpers"

interface Expense {
  id: string
  code: string
  reason: string | null
  status: string
  headcount: number
  attachment_count: number
}

test("新建报销：勾选参与人自动算人数 → 选票据自动保存草稿 → 提交，超标进入主管审批", async ({ page, request }) => {
  await loginAs(page, "sales")
  const api = await Api.as(request, "sales")
  const reason = uniq("浏览器测试 客户晚餐")

  await page.goto("/expenses")
  await page.getByRole("button", { name: "新建报销" }).click()
  const sheet = page.getByRole("dialog", { name: "新建报销" })
  await expect(sheet).toBeVisible()

  await sheet.locator("#exp-amount").fill("860")

  // 选客户 → 出现该客户的联系人，勾选客户方参与人（不再手写「客户：xx；我方：xx」）
  await sheet.getByRole("combobox").filter({ hasText: "搜索并选择客户" }).click()
  await page.getByPlaceholder("输入客户名称…").fill("明理")
  await page.getByRole("option", { name: /深圳明理律师事务所/ }).click()
  const contacts = sheet.getByRole("group", { name: "客户方参与人" })
  await contacts.getByRole("button", { name: /王律师/ }).click()
  await expect(contacts.getByRole("button", { name: /王律师/ })).toHaveAttribute("aria-pressed", "true")
  await sheet.locator("#exp-extra-guests").fill("2")

  // 人数自动计算：王律师 + 我 + 其他 2 人 = 4 人，人均 ¥215
  await expect(sheet.getByTestId("expense-headcount")).toContainText("共 4 人")
  await expect(sheet.getByTestId("expense-headcount")).toContainText("215")

  await sheet.locator("#exp-reason").fill(reason)

  // 选票据文件时自动保存草稿再上传（不再强制先点「保存草稿」）
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles({ name: "电子发票.pdf", mimeType: "application/pdf", buffer: PDF })
  await expect(page.getByText("电子发票.pdf", { exact: true })).toBeVisible()

  const submit = page.getByRole("button", { name: "提交审批" })
  await expect(submit).toBeDisabled() // 客户招待还缺小票

  await page.getByRole("combobox", { name: "票据类型" }).click()
  await page.getByRole("option", { name: "小票" }).click()
  await fileInput.setInputFiles({ name: "消费小票.png", mimeType: "image/png", buffer: PNG })
  await expect(page.getByText("消费小票.png", { exact: true })).toBeVisible()

  await expect(submit).toBeEnabled()
  await submit.click()
  const confirm = page.getByRole("alertdialog", { name: "提交报销审批" })
  await confirm.getByRole("button", { name: "确认提交" }).click()
  await expect(page.getByText("超出报销标准，已提交主管审批")).toBeVisible()

  const list = await api.call<{ items: Expense[] }>("GET", "/api/expenses?page_size=50")
  const saved = list.items.find((e) => e.reason === reason)
  expect(saved?.status).toBe("pending_approval")
  expect(saved?.headcount).toBe(4)
  expect(saved?.attachment_count).toBe(2)
})

test("不支持的文件类型被拒绝，不出现在票据列表里", async ({ page, request }) => {
  await loginAs(page, "sales")
  const api = await Api.as(request, "sales")
  const draft = await entertainmentDraft(api, 30_000, 2, uniq("浏览器测试 错误文件"))

  await page.goto("/expenses")
  await page.getByText(draft.code).first().click()
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles({ name: "病毒.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") })

  await expect(page.getByText("病毒.exe", { exact: true })).toHaveCount(0)
  expect((await api.call<Expense>("GET", `/api/expenses/${draft.id}`)).attachment_count).toBe(0)
})
