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

test.describe("审查 v9：日报", () => {
  test("销售看到当天记录、生成草稿并提交；主管在团队日报里看到内容", async ({ page, request }) => {
    test.setTimeout(120_000)
    const api = await Api.as(request, "sales")
    const name = uniq("E2E日报客户")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name, level: "B" })
    await api.call("POST", `/api/customers/${customer.id}/followups`, {
      type: "phone",
      content: "电话沟通部署方案，客户下周安排技术交流",
    })
    await loginAs(page, "sales")
    await page.goto("/reports")
    const facts = page.getByRole("region", { name: "当天记录" })
    await expect(facts).toContainText(name)
    await page.getByRole("button", { name: "AI 生成草稿" }).click()
    // 当天已有草稿（之前跑过）时会先确认覆盖
    const overwrite = page.getByRole("button", { name: "覆盖并生成" })
    await overwrite.waitFor({ timeout: 3_000 }).then(
      () => overwrite.click(),
      () => undefined,
    )
    const editor = page.getByRole("textbox", { name: "日报正文" })
    await expect(editor).not.toHaveValue("", { timeout: 90_000 })
    const marker = uniq("E2E日报标记")
    await editor.fill(`${await editor.inputValue()}\n${marker}`)
    await page.getByRole("button", { name: /^(提交|更新并提交)$/ }).click()
    await expect(page.getByText("已提交", { exact: true })).toBeVisible()

    await loginAs(page, "manager")
    await page.goto("/reports")
    await page.getByRole("tab", { name: "团队日报" }).click()
    const team = page.getByRole("list", { name: "团队日报" })
    await team.getByRole("button", { name: "张晨 的日报" }).click()
    await expect(team).toContainText(marker)
  })
})

test.describe("审查 v9：企业微信推送", () => {
  test("管理员配置群机器人：只接受企业微信地址、保存后脱敏显示（关闭推送，不向外发消息）", async ({
    page,
    request,
  }) => {
    await loginAs(page, "admin")
    await page.goto("/settings/integrations")
    const url = page.getByLabel("Webhook 地址")
    await url.fill("http://127.0.0.1:8000/internal")
    await page.getByRole("button", { name: "保存", exact: true }).click()
    await expect(page.getByText(/请粘贴企业微信群机器人的 Webhook 地址/)).toBeVisible()

    await page.getByRole("switch", { name: "开启推送" }).click() // 关闭：演示期间不实际推送
    await url.fill("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e2e00000-fake-0000-9999")
    await page.getByRole("button", { name: "保存", exact: true }).click()
    await expect(page.getByText("已配置")).toBeVisible()
    await expect(page.getByText(/…key=e2e0\*\*\*\*9999/)).toBeVisible()
    await expect(page.getByText("e2e00000-fake")).toHaveCount(0)

    const admin = await Api.as(request, "admin")
    await admin.call("PUT", "/api/integrations/wecom", {
      webhook_url: "",
      enabled: true,
      events: ["approval_pending", "deal_won", "report_summary", "report_remind"],
    })
    const sales = await Api.as(request, "sales")
    const flags = await sales.call<Record<string, boolean>>("GET", "/api/integrations/flags")
    expect(Object.values(flags).every((v) => v === false)).toBe(true)
  })
})

test.describe("审查 v9：外部情报", () => {
  test("客户详情有外部情报页签，明确标注演示数据并提示相关招标", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const name = uniq("E2E情报客户")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name, level: "B", industry: "律所" })
    await loginAs(page, "sales")
    await page.goto(`/customers/${customer.id}`)
    await page.getByRole("tab", { name: "外部情报" }).click()
    await expect(page.getByText("演示数据", { exact: true })).toBeVisible()
    await expect(page.getByText(/不是真实的工商、舆情或招投标信息/)).toBeVisible()
    const tenders = page.getByRole("region", { name: "招投标" })
    await expect(tenders.getByRole("listitem")).toHaveCount(3)
    await expect(tenders).toContainText(name)
    await expect(page.getByRole("region", { name: "工商信息" })).toContainText("统一社会信用代码")
  })
})

test.describe("审查 v9：AI 用量", () => {
  test("销售用 AI 后，主管在 AI 用量里看到该成员和功能；销售无权查看", async ({ page, request }) => {
    test.setTimeout(120_000)
    const sales = await Api.as(request, "sales")
    const customer = await sales.call<{ id: string }>("POST", "/api/customers", {
      name: uniq("E2E用量客户"),
      level: "B",
    })
    await sales.call("POST", `/api/customers/${customer.id}/followups`, { type: "phone", content: "确认试点范围" })
    const draft = await sales.call<{ source: string }>("POST", "/api/reports/daily/draft", {})
    test.skip(draft.source !== "ai", "大模型不可用，没有产生 AI 调用")

    await loginAs(page, "manager")
    await page.goto("/settings/ai-usage")
    await page.getByRole("radio", { name: "近 7 天" }).click()
    await expect(page.getByRole("region", { name: "按人员" })).toContainText("张晨")
    await expect(page.getByRole("region", { name: "按功能" })).toContainText("日报草稿")
    await expect(page.getByRole("region", { name: "每日用量" })).toBeVisible()

    await loginAs(page, "sales")
    await page.goto("/settings/ai-usage")
    await expect(page.getByText("AI 用量统计仅主管和管理员可以查看")).toBeVisible()
  })
})
