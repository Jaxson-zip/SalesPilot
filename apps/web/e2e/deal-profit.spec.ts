import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

test("商机详情：这单赚多少 = 报价毛利 − 预估提成 − 跟单费用（只读，接口数据注入）", async ({ page }) => {
  await loginAs(page, "sales")
  // 只改返回给页面的数据，不写库
  await page.route(/\/api\/opportunities\/[0-9a-f-]{36}$/, async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    body.data.profit = {
      quote_id: "q-1",
      quote_code: "Q-2026-099",
      basis: "latest",
      price: 15_000_000,
      gross: 6_000_000,
      commission: 700_000,
      expenses: 86_000,
      net: 5_214_000,
    }
    await route.fulfill({ response: res, json: body })
  })
  await page.goto("/pipeline")
  await page.getByText("合同审查私有化", { exact: true }).first().click()
  const box = page.getByRole("region", { name: "这单赚多少" })
  await expect(box).toContainText("按最新报价估算 Q-2026-099")
  await expect(box).toContainText("报价毛利¥60,000")
  await expect(box).toContainText("预估提成−¥7,000")
  await expect(box).toContainText("跟单费用−¥860")
  await expect(box).toContainText("预计赚¥52,140")
  await expect(box).toContainText("34.8%")
})
