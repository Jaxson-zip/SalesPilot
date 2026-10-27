import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

/**
 * 规则说明和格式说明用悬浮卡片，不再弹整屏侧栏（回归：提成规则曾是一个几乎空白的侧栏）。
 * 卡片要：不遮挡页面、有具体数字（来自后端 rules.yaml）、按 Esc 关闭。
 */
test.describe("说明类内容用悬浮卡片", () => {
  test("合同页「提成规则」：悬浮显示具体比例，不打开侧栏", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/contracts")
    const trigger = page.getByRole("button", { name: "提成规则" })
    await trigger.hover()
    const card = page.getByRole("dialog", { name: "提成规则" }).or(page.getByLabel("提成规则"))
    await expect(card).toBeVisible()
    await expect(card).toContainText("硬件提成")
    await expect(card).toContainText(/%/)
    await expect(card).toContainText("rules.yaml")
    // 没有打开整屏侧栏
    await expect(page.getByRole("dialog", { name: /合同与提成 ·/ })).toHaveCount(0)
    await page.keyboard.press("Escape")
    await expect(card).toBeHidden()
  })

  test("报销页「报销标准」：金额来自后端规则", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/expenses")
    await page.getByRole("button", { name: "报销标准" }).click()
    const card = page.getByLabel("报销标准").or(page.getByRole("dialog", { name: "报销标准" }))
    await expect(card).toContainText("人均 ¥150")
    await expect(card).toContainText("¥500/晚")
  })

  test("报销上传区「格式说明与样例」：列出格式、要求和样例下载", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/expenses")
    await page.getByRole("button", { name: "新建报销" }).click()
    const sheet = page.getByRole("dialog", { name: "新建报销" })
    await sheet.getByRole("button", { name: "格式说明与样例" }).click()
    // 悬浮卡片是 portal 到 body 的，不在侧栏子树里
    const card = page.getByLabel("票据格式说明")
    await expect(card).toContainText("JPG / PNG / PDF")
    await expect(card).toContainText("10 MB")
    await expect(card.getByRole("link", { name: "下载电子发票样例" })).toHaveAttribute(
      "href",
      "/samples/invoice-sample.pdf",
    )
    await expect(card.getByRole("link", { name: "下载消费小票样例" })).toHaveAttribute(
      "href",
      "/samples/receipt-sample.png",
    )
    // 样例图能被浏览器加载（文件真实存在）
    const img = card.getByRole("img", { name: "电子发票样例" })
    await expect(img).toHaveJSProperty("complete", true)
    expect(await img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0)
  })

  test("行业包知识库：标出会入库的格式，并给出格式说明", async ({ page }) => {
    await loginAs(page, "admin")
    await page.goto("/settings/packs")
    await page
      .getByRole("button", { name: /知识库/ })
      .nth(1)
      .click()
    const sheet = page.getByRole("dialog", { name: /知识库/ })
    await expect(sheet).toContainText(/xlsx/i)
    await expect(sheet).toContainText("不入库")
    await sheet.getByRole("button", { name: "支持的格式与样例" }).click()
    const card = page.getByLabel("知识库文档格式")
    for (const text of ["PDF", "XLSX", "MD"]) await expect(card).toContainText(new RegExp(text, "i"))
    await expect(card.getByRole("link", { name: /下载.*样例/ })).toHaveCount(3)
  })
})
