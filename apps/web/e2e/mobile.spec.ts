import { expect, test } from "@playwright/test"

import { Api, loginAs } from "./helpers"

// 手机尺寸（iPhone 14 左右）：主要页面不出现横向滚动；打印页按屏宽缩放 A4 纸面（只读）
test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

test("手机上主要页面不横向溢出，打印页整页缩放显示", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const quote = (await api.call<{ items: { id: string }[] }>("GET", "/api/quotes?page_size=1")).items[0]
  if (!quote) throw new Error("演示数据里没有报价单，请先运行 seed")
  await loginAs(page, "sales")
  for (const path of ["/dashboard", "/ai", "/customers", "/pipeline", "/quotes", `/quotes/${quote.id}`, "/contracts"]) {
    await page.goto(path)
    await expect(page.locator("main").first()).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, path).toBeLessThanOrEqual(0)
  }
  // 抽屉导航可以打开
  await page.goto("/dashboard")
  await page
    .getByRole("button", { name: /菜单|导航|侧栏/ })
    .first()
    .click()
  await expect(page.getByRole("link", { name: "客户" }).first()).toBeVisible()

  await page.goto(`/quotes/${quote.id}/print`)
  const sheet = page.locator(".print-sheet").first()
  await expect(sheet).toBeVisible()
  const box = await sheet.boundingBox()
  expect(box!.width).toBeLessThanOrEqual(390)
  expect(box!.width).toBeGreaterThan(300) // 是缩放后的整张 A4，不是被挤压的窄栏
})
