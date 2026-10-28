import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const NOTES = `10 月 27 日 深圳明理律师事务所 拜访纪要
参会：周律师（主任，最终拍板）、陈工（IT 负责人，13900002222）
需求：内网部署大模型做合同审查，预算 60 万左右，明年 1 月前上线
顾虑：数据不能出内网；担心律师不会用
约定：下周一发方案，下周三安排一次演示`

test.describe("审查 v9：一手材料一键消化", () => {
  test("上传纪要 → AI 整理成跟进 / 联系人 / 下一步，一张确认卡片（取消，不改演示数据）", async ({ page }) => {
    test.setTimeout(180_000)
    await loginAs(page, "sales")
    await page.goto("/ai")
    await page.getByTestId("material-input").setInputFiles({
      name: "明理拜访纪要.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(NOTES, "utf-8"),
    })
    await expect(page.getByText("明理拜访纪要.txt")).toBeVisible()
    await page.getByRole("button", { name: "发送" }).click()
    // 用户气泡只显示材料名，不显示原文
    await expect(page.getByText(/\d+ 字/).first()).toBeVisible()
    const confirm = page.getByRole("button", { name: "确认执行" })
    await expect(confirm).toBeVisible({ timeout: 150_000 })
    await expect(page.getByText("联系人").first()).toBeVisible()
    await expect(page.getByText(/周律师/).first()).toBeVisible()
    await expect(page.getByText("下一步").first()).toBeVisible()
    await page.getByRole("button", { name: "取消" }).click()
    await expect(confirm).toHaveCount(0)
  })
})
