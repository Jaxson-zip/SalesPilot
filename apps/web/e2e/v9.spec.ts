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

test.describe("审查 v9：MEDDIC 赢单辅导", () => {
  test("商机侧栏：赢单要素可标注、阶段风险提示、AI 评估给出建议", async ({ page, request }) => {
    test.setTimeout(120_000)
    const api = await Api.as(request, "sales")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name: uniq("E2E赢单客户"), level: "A" })
    const opp = await api.call<{ id: string }>("POST", "/api/opportunities", {
      customer_id: customer.id,
      name: uniq("E2E赢单商机"),
      amount: 300_000_00,
    })
    await api.call("PATCH", `/api/opportunities/${opp.id}/stage`, { stage: "qualified" })
    await api.call("POST", `/api/customers/${customer.id}/followups`, {
      type: "visit",
      content: "客户反馈合同审查靠人工，效率低；预算由周律师拍板",
    })
    await loginAs(page, "sales")
    await page.goto(`/pipeline?opp=${opp.id}`)
    const card = page.getByRole("region", { name: "赢单要素" })
    await expect(card).toBeVisible()
    await expect(card).toContainText("当前阶段还没确认：痛点")
    await expect(card).toContainText("建议问")

    await card.getByRole("button", { name: /痛点：缺失/ }).click()
    await card.getByRole("radio", { name: "已确认" }).click()
    await card.getByRole("textbox", { name: "痛点 证据" }).fill("合同审查靠人工，每月积压")
    await card.getByRole("button", { name: "保存" }).click()
    await expect(card.getByRole("button", { name: /痛点：已确认/ })).toBeVisible()
    await expect(card).not.toContainText("当前阶段还没确认")

    await card.getByRole("button", { name: "AI 评估" }).click()
    await expect(card.getByRole("button", { name: /采纳 \d+ 项|忽略/ }).first()).toBeVisible({ timeout: 90_000 })
  })
})

test.describe("审查 v9：竞品战卡", () => {
  test("销售按客户原话搜战卡，在商机里标注竞品后直接看应对话术", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name: uniq("E2E战卡客户"), level: "B" })
    const opp = await api.call<{ id: string }>("POST", "/api/opportunities", {
      customer_id: customer.id,
      name: uniq("E2E战卡商机"),
      amount: 100_000_00,
    })
    await loginAs(page, "sales")
    await page.goto("/battlecards")
    await page.getByRole("textbox", { name: "搜索竞品战卡" }).fill("自己搭")
    const list = page.getByRole("list", { name: "竞品战卡" })
    await expect(list.getByRole("button", { name: /客户自建/ })).toBeVisible()
    await expect(list).toContainText("3 个月内上线")
    await expect(page.getByRole("button", { name: "新建战卡" })).toHaveCount(0)

    await page.goto(`/pipeline?opp=${opp.id}`)
    const card = page.getByRole("region", { name: "竞争对手" })
    await card.getByRole("button", { name: "标注竞品" }).click()
    await page.getByRole("menuitemcheckbox", { name: "公有云大模型 API" }).click()
    await page.keyboard.press("Escape")
    await card.getByRole("button", { name: "公有云大模型 API 应对话术" }).click()
    await expect(card).toContainText("云上 API 便宜多了")
    await expect(card).toContainText("我们怎么赢")
  })

  test("管理员新建战卡，销售能搜到", async ({ page, request }) => {
    const name = uniq("E2E竞品")
    await loginAs(page, "admin")
    await page.goto("/battlecards")
    await page.getByRole("button", { name: "新建战卡" }).click()
    await page.getByRole("textbox", { name: "竞品名称" }).fill(name)
    await page.getByRole("textbox", { name: "他们的弱点" }).fill("售后响应慢")
    await page.getByRole("textbox", { name: "说法 1" }).fill("他们送一年免费维保")
    await page.getByRole("textbox", { name: "应对 1" }).fill("我们的维保含驻场，算下来更划算")
    await page.getByRole("button", { name: "保存" }).click()
    await expect(page.getByRole("button", { name: `${name} 战卡` })).toBeVisible()

    const api = await Api.as(request, "sales")
    const hits = await api.call<{ name: string; id: string }[]>(
      "GET",
      `/api/competitors?q=${encodeURIComponent("免费维保")}`,
    )
    expect(hits.map((h) => h.name)).toContain(name)
    const admin = await Api.as(request, "admin")
    await admin.call("DELETE", `/api/competitors/${hits.find((h) => h.name === name)!.id}`)
  })
})
