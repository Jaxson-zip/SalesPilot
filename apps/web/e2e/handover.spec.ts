import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

test("按人交接：主管选交接人看预览，选接手人后确认（模拟接口，不改真实数据）", async ({ page }) => {
  await loginAs(page, "manager")
  const calls: Record<string, unknown>[] = []
  await page.route(/\/api\/customers\/handover\/preview\?/, (r) =>
    r.fulfill(ok({ customers: 3, opportunities: 2, tasks: 4, quotes: 1, contracts: 1 })),
  )
  await page.route(/\/api\/customers\/handover$/, (r) => {
    calls.push(r.request().postDataJSON())
    return r.fulfill(ok({ customers: 3, opportunities: 2, tasks: 4, quotes: 1, contracts: 1 }))
  })
  await page.goto("/customers")
  await page.getByRole("button", { name: "按人交接" }).click()
  const dialog = page.getByRole("dialog", { name: "按人交接" })
  const confirm = dialog.getByRole("button", { name: "确认交接" })
  await expect(confirm).toBeDisabled()

  await dialog.getByRole("combobox", { name: "交接人" }).click()
  await page.getByRole("option", { name: "张晨" }).click()
  await expect(dialog.getByRole("status")).toHaveText(
    "张晨名下：3 个客户、2 个进行中的商机、1 份未成交的报价、4 个未完成的任务、1 份回款中的合同。",
  )
  await expect(confirm).toBeDisabled() // 还没选接手人

  await dialog.getByRole("combobox", { name: "接手人" }).click()
  await expect(page.getByRole("option", { name: "张晨" })).toHaveCount(0) // 不能交接给自己
  await page.getByRole("option", { name: "王磊" }).click()
  await confirm.click()
  await expect.poll(() => calls.length).toBe(1)
  expect(Object.keys(calls[0]).sort()).toEqual(["from_user_id", "to_user_id"])
  await expect(page.getByText("已把张晨的客户交接给王磊")).toBeVisible()
  await expect(dialog).toBeHidden()
})

test("按人交接：销售看不到入口", async ({ page }) => {
  await loginAs(page, "sales")
  await page.goto("/customers")
  await expect(page.getByRole("button", { name: "新建客户" })).toBeVisible()
  await expect(page.getByRole("button", { name: "按人交接" })).toHaveCount(0)
})
