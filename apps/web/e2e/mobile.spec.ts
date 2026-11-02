import { expect, type Page, test } from "@playwright/test"

import { Api, loginAs } from "./helpers"

// 手机尺寸（iPhone 14 左右）：主要页面不出现横向滚动；打印页按屏宽缩放 A4 纸面（只读）
test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

/**
 * main 里超出屏幕右边的可见元素（不在横向滚动容器里）。
 * 回归：AI 工作台新对话的输入框工具栏把整列撑到约 420px，外层卡片 overflow-hidden 把右边裁掉，
 * 页面本身不出现横向滚动，只看 scrollWidth 查不出来。
 */
async function clippedInMain(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const width = window.innerWidth
    const inScroller = (el: Element) => {
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX
        if (ox === "auto" || ox === "scroll") return true
      }
      return false
    }
    return [...document.querySelectorAll("main *")]
      .filter((el) => {
        const r = el.getBoundingClientRect()
        const style = getComputedStyle(el)
        if (r.width < 1 || r.height < 1 || r.right <= width + 1) return false
        return style.visibility !== "hidden" && style.position !== "fixed" && !inScroller(el)
      })
      .slice(0, 3)
      .map(
        (el) =>
          `${el.tagName}.${String(el.className).slice(0, 60)} right=${Math.round(el.getBoundingClientRect().right)}`,
      )
  })
}

test("手机上主要页面不横向溢出，打印页整页缩放显示", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const quotes = (await api.call<{ items: { id: string; status: string }[] }>("GET", "/api/quotes?page_size=50")).items
  // 审批通过后才能打印，选一张能打印的
  const quote = quotes.find((q) => ["approved", "sent", "accepted"].includes(q.status))
  if (!quote) throw new Error("演示数据里没有已审批的报价单，请先运行 seed")
  await loginAs(page, "sales")
  const paths = ["/dashboard", "/ai", "/customers", "/pipeline", "/quotes", `/quotes/${quote.id}`, "/contracts"]
  // 320：最窄的常见手机；390：主流尺寸
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 })
    for (const path of paths) {
      await page.goto(path)
      await expect(page.locator("main").first()).toBeVisible()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      expect(overflow, `${width} ${path}`).toBeLessThanOrEqual(0)
      expect(await clippedInMain(page), `${width} ${path}`).toEqual([])
    }
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
