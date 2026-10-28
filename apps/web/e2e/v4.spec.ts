import { expect, test, type Page } from "@playwright/test"

import { Api, loginAs, uniq } from "./helpers"

interface Expense {
  id: string
  reason: string | null
  type: string
  details: { city?: string | null; check_in?: string | null; check_out?: string | null } | null
  policy_check: { unit?: string; over_amount: number } | null
}

async function mingliId(api: Api): Promise<string> {
  const list = await api.call<{ items: { id: string; name: string }[] }>(
    "GET",
    "/api/customers?view=mine&q=深圳明理&page_size=50",
  )
  const c = list.items.find((x) => x.name === "深圳明理律师事务所")
  if (!c) throw new Error("演示数据缺少深圳明理律师事务所")
  return c.id
}

/** 在日期选择器里选当前月份的某一天（日历默认打开当前月） */
async function pickDay(page: Page, label: string, day: number): Promise<void> {
  await page.getByRole("button", { name: label }).click()
  await page
    .getByRole("grid")
    .getByRole("button", { name: new RegExp(`月${day}日`) })
    .click()
  await expect(page.getByRole("grid")).toHaveCount(0) // 等日历收起动画结束，再打开下一个
}

test.describe("v4：报销模板与差旅住宿", () => {
  test("从「出差住宿」模板开始：带出类型和事由，按城市和晚数校验每晚标准", async ({ page, request }) => {
    await loginAs(page, "sales")
    const api = await Api.as(request, "sales")
    const reason = uniq("出差住宿：深圳客户方案评审")

    await page.goto("/expenses")
    await page.getByRole("button", { name: "新建报销" }).click()
    const sheet = page.getByRole("dialog", { name: "新建报销" })

    await sheet.getByRole("group", { name: "报销模板" }).getByRole("button", { name: "出差住宿" }).click()
    await expect(sheet.getByRole("combobox", { name: "费用类型" })).toContainText("差旅住宿")
    await expect(sheet.locator("#exp-reason")).toHaveValue("出差住宿：")
    // 报销须知随类型变化，标准金额来自 rules.yaml
    await expect(sheet.getByRole("region", { name: "报销须知" })).toContainText("每晚 500 元")
    // 住宿不需要填参与人
    await expect(sheet.getByRole("group", { name: "客户方参与人" })).toHaveCount(0)

    await sheet.locator("#exp-amount").fill("1200")
    await sheet.locator("#exp-city").fill("深圳")
    await pickDay(page, "入住日期", 10)
    await pickDay(page, "离店日期", 12)
    await expect(sheet.getByTestId("expense-nights")).toHaveText("共 2 晚，每晚 ¥600")
    await expect(sheet.getByText("超出报销标准，需主管审批")).toBeVisible()

    await sheet.locator("#exp-reason").fill(reason)
    await sheet.getByRole("button", { name: "保存草稿", exact: true }).click()
    await expect(page.getByText("草稿已保存").first()).toBeVisible()

    const list = await api.call<{ items: Expense[] }>("GET", "/api/expenses?page_size=50")
    const saved = list.items.find((e) => e.reason === reason)
    expect(saved?.type).toBe("hotel")
    const detail = await api.call<Expense>("GET", `/api/expenses/${saved?.id}`)
    expect(detail.details?.city).toBe("深圳")
    expect(detail.policy_check).toMatchObject({ unit: "night", over_amount: 20_000 })
  })

  test("住宿没填城市时提示到字段上，不保存", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/expenses")
    await page.getByRole("button", { name: "新建报销" }).click()
    const sheet = page.getByRole("dialog", { name: "新建报销" })
    await sheet.getByRole("group", { name: "报销模板" }).getByRole("button", { name: "出差住宿" }).click()
    await sheet.locator("#exp-amount").fill("300")
    await sheet.locator("#exp-reason").fill("出差住宿：测试")
    await sheet.getByRole("button", { name: "保存草稿", exact: true }).click()
    await expect(sheet.getByText("请填写住宿城市")).toBeVisible()
    await expect(sheet).toBeVisible()
  })
})

test("v4：跟进模板——插入后要填写内容才能保存", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const id = await mingliId(api)
  await loginAs(page, "sales")
  await page.goto(`/customers/${id}`)

  await page.getByRole("group", { name: "跟进模板" }).getByRole("button", { name: "电话沟通" }).click()
  const box = page.getByRole("textbox", { name: "跟进内容" })
  await expect(box).toHaveValue(/^沟通对象：\n客户需求/)
  const save = page.getByRole("button", { name: "保存", exact: true })
  await expect(save).toBeDisabled()
  await expect(page.getByText("模板还没填写内容")).toBeVisible()

  await box.fill(`沟通对象：王律师\n客户需求 / 关注点：${uniq("下周看演示")}\n下一步：发送演示邀请`)
  await expect(save).toBeEnabled()
})

test("v4：输单弹窗——点选常见原因后再补充说明", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const opp = await api.call<{ id: string; name: string }>("POST", "/api/opportunities", {
    customer_id: await mingliId(api),
    name: uniq("输单原因测试"),
    amount: 500_000,
  })
  await loginAs(page, "sales")
  await page.goto(`/pipeline?opp=${opp.id}`)
  await page.getByRole("button", { name: /标记为输单/ }).click()

  const dialog = page.getByRole("dialog", { name: "标记为输单" })
  await dialog.getByRole("group", { name: "常见输单原因" }).getByRole("button", { name: "选择了竞品" }).click()
  await expect(dialog.getByRole("textbox")).toHaveValue("选择了竞品")
  await dialog.getByRole("button", { name: "取消", exact: true }).click()
  await expect(dialog).toBeHidden()
})

test("v4：使用说明页——按角色的上手步骤，报销标准来自规则", async ({ page }) => {
  await loginAs(page, "manager")
  await page.goto("/dashboard")
  await page.getByRole("link", { name: "使用说明" }).click()
  await expect(page).toHaveURL(/\/help$/)
  await expect(page.getByRole("heading", { name: "主管：每天这样用" })).toBeVisible()
  await expect(page.getByRole("region", { name: "报销怎么填" })).toContainText("每晚 500 元")
  await expect(page.getByRole("region", { name: "报销怎么填" })).toContainText("人均 150 元")
})

/** 固定 /api/agent/models 的返回，测试不受本机 .env 里有没有 Key 影响 */
async function mockModels(page: Page, deepseek: boolean): Promise<void> {
  const items = [
    { id: "deepseek-chat", type: "model", available: deepseek, members: [] },
    { id: "qwen-plus", type: "model", available: false, members: [] },
    { id: "chat-default", type: "group", available: deepseek, members: ["deepseek-chat"] },
    { id: "chat-agent", type: "group", available: deepseek, members: ["qwen-plus", "deepseek-chat"] },
  ]
  const data = { items, default: "chat-agent", any_available: deepseek, gateway_ok: true }
  await page.route("**/api/agent/models", (route) =>
    route.fulfill({ json: { code: 0, message: "ok", data, request_id: "e2e" } }),
  )
}

test("v4：AI 欢迎页按角色给示例问题；没配模型时提示规则模式", async ({ page }) => {
  await mockModels(page, false)
  await loginAs(page, "manager")
  await page.goto("/ai")
  await expect(page.getByRole("button", { name: /待审批/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /对话报销/ })).toHaveCount(0)
  await expect(page.getByText("规则模式")).toBeVisible()
})

test("模型选择：写明当前用哪个模型，未配 Key 的不可选，不露出内部分组 ID", async ({ page }) => {
  await mockModels(page, true)
  await loginAs(page, "sales")
  await page.goto("/ai")
  const select = page.getByRole("combobox", { name: "选择模型" })
  await expect(select).toContainText("自动")
  await expect(select).toContainText("当前 DeepSeek") // 分组第一个 qwen 没配 Key，实际用的是 DeepSeek
  await expect(page.getByText("规则模式")).toHaveCount(0)
  await select.click()
  await expect(page.getByRole("option", { name: /Qwen/ })).toHaveAttribute("aria-disabled", "true")
  await expect(page.getByRole("option", { name: /chat-default/ })).toHaveCount(0)
})
