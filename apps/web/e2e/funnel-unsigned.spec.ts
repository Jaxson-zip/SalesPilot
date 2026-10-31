import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

test("工作台漏斗：手工标的赢单还没签合同时单独提示（接口数据注入，不写库）", async ({ page }) => {
  await loginAs(page, "sales")
  await page.route(/\/api\/dashboard(\?.*)?$/, async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    for (const s of body.data.funnel) {
      if (s.stage === "won") Object.assign(s, { unsigned_count: 2, unsigned_amount: 3_500_000 })
    }
    await route.fulfill({ response: res, json: body })
  })
  await page.goto("/dashboard")
  await expect(page.getByText("赢单里有 2 个还没签合同（¥35,000），不计入本月成交")).toBeVisible()
  if (process.env.SHOT_DIR) await page.screenshot({ path: `${process.env.SHOT_DIR}/funnel.png`, fullPage: true })
})
