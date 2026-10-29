import { expect, test } from "@playwright/test"

import { Api, loginAs } from "./helpers"

test("从回款计划打开合同要素确认单：双方、金额大写、回款计划、签字栏（只读）", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const list = await api.call<{ items: { id: string; code: string; customer: { name: string } | null }[] }>(
    "GET",
    "/api/contracts?page_size=1",
  )
  const c = list.items[0]
  if (!c) throw new Error("演示数据里没有合同，请先运行 seed")
  await loginAs(page, "sales")
  await page.goto(`/contracts?plan=${c.id}`)
  await page.getByRole("link", { name: "打印合同要素确认单" }).click()

  await expect(page).toHaveURL(new RegExp(`/contracts/${c.id}/print$`))
  await expect(page.getByText("合同要素确认单", { exact: true })).toBeVisible()
  await expect(page.getByText(c.code, { exact: true })).toBeVisible()
  if (c.customer) await expect(page.getByText(c.customer.name).first()).toBeVisible()
  await expect(page.getByText(/^[零壹贰叁肆伍陆柒捌玖拾佰仟万亿元角分整]+$/).first()).toBeVisible()
  await expect(page.getByRole("region", { name: "回款计划" })).toBeVisible()
  await expect(page.getByRole("region", { name: "确认单说明" })).toContainText("正式合同")
  await expect(page.getByText("甲方（盖章）")).toBeVisible()
  await expect(page).toHaveTitle(new RegExp(`^合同要素确认单-${c.code}`))
  await page.getByRole("link", { name: "返回合同" }).click()
  await expect(page).toHaveURL(/\/contracts/)
})
