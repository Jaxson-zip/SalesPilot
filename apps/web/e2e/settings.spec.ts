import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

/** 网页上维护配置：每个用例都把改动恢复默认，不污染演示数据 */
test.describe("业务规则与行业包（网页维护）", () => {
  test("业务规则：改毛利底线 → 显示已修改与默认值 → 恢复默认", async ({ page }) => {
    await loginAs(page, "admin")
    await page.goto("/settings/rules")
    // 第一组是「工作方式」（个人模式开关），先切到报价与审批
    await page.getByRole("tablist", { name: "规则分组" }).getByRole("tab", { name: /报价与审批/ }).click()
    const group = page.getByRole("region", { name: "报价与审批" })
    await expect(group).toContainText("毛利底线")
    await group.getByRole("button", { name: "编辑报价与审批" }).click()
    await group.getByRole("textbox", { name: "毛利底线" }).fill("95")
    await group.getByRole("button", { name: "保存" }).click()
    await expect(group.getByRole("alert")).toContainText("要在")
    await group.getByRole("textbox", { name: "毛利底线" }).fill("22")
    await group.getByRole("button", { name: "保存" }).click()
    await expect(group).toContainText("22%")
    await expect(group).toContainText("默认 25%")
    await group.getByRole("button", { name: "恢复默认" }).click()
    await page.getByRole("alertdialog").getByRole("button", { name: "恢复默认" }).click()
    await expect(group).not.toContainText("已修改")
    await expect(group).toContainText("25%")
  })

  test("行业包：改产品售价后恢复；业务规则不再显示英文键名", async ({ page }) => {
    await loginAs(page, "admin")
    await page.goto("/settings/packs")
    await page.getByRole("button", { name: "大模型部署 产品目录" }).click()
    const sheet = page.getByRole("dialog")
    await expect(sheet).toContainText("硬件")
    await sheet.getByRole("button", { name: "编辑 GPU 服务器 4× L20 48G" }).click()
    await sheet.getByRole("textbox", { name: "售价（元）" }).fill("300000")
    await sheet.getByRole("button", { name: "保存" }).click()
    await expect(sheet).toContainText("¥300,000")
    await expect(sheet).toContainText("默认 成本 ¥218,000 · 售价 ¥262,000")
    await sheet.getByRole("button", { name: "恢复默认" }).click()
    await expect(sheet).not.toContainText("¥300,000")
    await page.keyboard.press("Escape")

    await page.getByRole("button", { name: "大模型部署 业务规则" }).click()
    await expect(sheet).toContainText("显存余量系数")
    await expect(sheet).toContainText("方案档位")
    await expect(sheet).not.toContainText("expense.")
    await expect(sheet).not.toContainText("[object Object]")
  })

  test("知识库：上传文档后立即入库，可以删除（内置文档不能删）", async ({ page }) => {
    await loginAs(page, "admin")
    await page.goto("/settings/packs")
    await page.getByRole("button", { name: "企业办公 IT 知识库" }).click()
    const sheet = page.getByRole("dialog")
    const name = `e2e-${Date.now().toString(36)}.md`
    await sheet.getByLabel("选择要上传的文档").setInputFiles({
      name,
      mimeType: "text/markdown",
      buffer: Buffer.from("# 售后响应说明\n\n## 上门服务\n\n深圳市内工作日 4 小时上门，节假日 8 小时。"),
    })
    const row = sheet.getByRole("listitem", { name })
    await expect(row).toContainText(/已入库 \d+ 段/, { timeout: 60_000 })
    await sheet.getByRole("button", { name: `删除 ${name}` }).click()
    await page.getByRole("alertdialog").getByRole("button", { name: "确认删除" }).click()
    await expect(sheet.getByText(name)).toHaveCount(0)
    await expect(sheet.getByRole("button", { name: /^删除 / })).toHaveCount(0) // 内置文档没有删除按钮
  })
})
