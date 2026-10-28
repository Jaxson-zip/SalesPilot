import { expect, test } from "@playwright/test"

import { Api, loginAs, uniq } from "./helpers"

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

test.describe("审查 v9：数据安全（操作日志、电话脱敏、导出授权）", () => {
  test("联系人电话默认脱敏，点「查看」显示完整号码，主管在操作日志里看到记录", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const customer = await api.call<{ id: string; name: string }>("POST", "/api/customers", {
      name: uniq("E2E脱敏客户"),
      level: "B",
    })
    await api.call("POST", `/api/customers/${customer.id}/contacts`, { name: "钱经理", phone: "13700004444" })
    await loginAs(page, "sales")
    await page.goto(`/customers/${customer.id}`)
    await page.getByRole("tab", { name: "联系人" }).click()
    const row = page.getByRole("list", { name: "联系人列表" }).getByRole("listitem").filter({ hasText: "钱经理" })
    await expect(row).toContainText("137****4444")
    await expect(row).not.toContainText("13700004444")
    await row.getByRole("button", { name: "查看 钱经理 的完整电话" }).click()
    await expect(row.getByRole("link", { name: "13700004444" })).toBeVisible()

    await loginAs(page, "manager")
    await page.goto("/settings/audit")
    await page.getByRole("textbox", { name: "搜索操作日志" }).fill("钱经理")
    const log = page.getByRole("list", { name: "操作日志" }).getByRole("listitem").first()
    await expect(log).toContainText("查看联系人电话")
    await expect(log).toContainText("钱经理")
  })

  test("销售不能导出客户名单（服务端拒绝并留痕），可以导出报价单", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/customers")
    await page.getByRole("button", { name: "选项" }).click()
    await page.getByRole("menuitem", { name: "导出 CSV" }).click()
    await expect(page.getByText("当前角色不能导出客户").first()).toBeVisible()

    await page.goto("/quotes")
    const download = page.waitForEvent("download")
    await page.getByRole("button", { name: "选项" }).click()
    await page.getByRole("menuitem", { name: "导出 CSV" }).click()
    expect((await download).suggestedFilename()).toMatch(/\.csv$/)
  })
})
