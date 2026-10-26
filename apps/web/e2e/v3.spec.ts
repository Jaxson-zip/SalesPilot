import { expect, test } from "@playwright/test"

import { Api, artifactOf, entertainmentDraft, loginAs, PDF, PNG, uniq } from "./helpers"

interface Customer {
  id: string
  name: string
  owner: { id: string; name: string } | null
}
interface Opportunity {
  id: string
  name: string
  next_task: { title: string } | null
}
interface Task {
  id: string
  title: string
  done: boolean
}
interface Quote {
  id: string
  code: string
  status: string
  total_price: number
  discount_rate: number
}

async function mingli(api: Api): Promise<Customer> {
  const list = await api.call<{ items: Customer[] }>("GET", "/api/customers?view=mine")
  const c = list.items.find((x) => x.name === "深圳明理律师事务所")
  if (!c) throw new Error("演示数据缺少深圳明理律师事务所")
  return c
}

test.describe("v3：多选批量操作", () => {
  test("不勾选时没有批量按钮；勾选后出现批量操作栏，取消选择后消失", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/customers")
    await expect(page.getByRole("toolbar", { name: "批量操作" })).toHaveCount(0)
    await page.getByRole("checkbox", { name: "选择该行" }).first().check()
    const bar = page.getByRole("toolbar", { name: "批量操作" })
    await expect(bar).toBeVisible()
    await expect(bar.getByRole("button", { name: "导出所选" })).toBeVisible()
    await expect(bar.getByRole("button", { name: "转移负责人" })).toHaveCount(0) // 销售不能转移
    await bar.getByRole("button", { name: "取消选择" }).click()
    await expect(bar).toHaveCount(0)
  })

  test("主管批量转移客户负责人：确认后客户归新负责人", async ({ page, request }) => {
    const sales = await Api.as(request, "sales")
    const customer = await sales.call<Customer>("POST", "/api/customers", { name: uniq("转移测试客户") })

    await loginAs(page, "manager")
    await page.goto("/customers") // 主管默认看「团队客户」
    const row = page.getByRole("row").filter({ hasText: customer.name })
    await row.getByRole("checkbox", { name: "选择该行" }).check()
    await page.getByRole("toolbar", { name: "批量操作" }).getByRole("button", { name: "转移负责人" }).click()

    const dialog = page.getByRole("dialog", { name: "转移负责人" })
    await dialog.locator("#transfer-to").click()
    await page.getByRole("option", { name: /王磊/ }).click()
    await dialog.getByRole("button", { name: "确认转移" }).click()
    await expect(dialog).toBeHidden()

    const manager = await Api.as(request, "manager")
    await expect
      .poll(async () => (await manager.call<Customer>("GET", `/api/customers/${customer.id}`)).owner?.name)
      .toBe("王磊")
  })
})

test.describe("v3：下一步行动", () => {
  test("在商机侧栏添加下一步，卡片显示；勾选完成后可以撤销", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const customer = await mingli(api)
    const opp = await api.call<Opportunity>("POST", "/api/opportunities", {
      customer_id: customer.id,
      name: uniq("下一步测试"),
      amount: 1_000_000,
    })
    const title = uniq("电话确认预算")

    await loginAs(page, "sales")
    await page.goto(`/pipeline?opp=${opp.id}`)
    const sheet = page.getByRole("dialog").filter({ hasText: opp.name })
    await expect(sheet.getByText("未安排下一步")).toBeVisible()
    await sheet.getByRole("button", { name: "添加下一步" }).click()

    const dialog = page.getByRole("dialog", { name: "添加下一步" })
    await dialog.locator("#task-title").fill(title)
    await dialog.getByRole("button", { name: "明天" }).click()
    await dialog.getByRole("button", { name: "添加", exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(sheet.getByText(title)).toBeVisible()
    await expect
      .poll(async () => (await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).next_task?.title)
      .toBe(title)

    // 勾选即完成（受控复选框，完成后该行消失），toast 里可以撤销
    const done = sheet.getByRole("checkbox", { name: `完成：${title}` })
    await done.click()
    await expect(done).toHaveCount(0)
    await expect(sheet.getByText(/完成了任务/).first()).toBeVisible() // 动态显示中文，不是 task_done
    await page.getByRole("button", { name: "撤销" }).click()
    await expect(done).toBeVisible()
    await expect
      .poll(async () => {
        const list = await api.call<{ items: Task[] }>(
          "GET",
          `/api/tasks?subject_type=opportunity&subject_id=${opp.id}&status=open`,
        )
        return list.items.some((t) => t.title === title)
      })
      .toBe(true)
  })

  test("工作台待办显示今天到期和已逾期的任务", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/dashboard")
    await expect(page.getByText("待办").first()).toBeVisible()
    await expect(page.getByText(/逾期/).first()).toBeVisible()
  })
})

test.describe("v3：报价调价与打印", () => {
  async function draftQuote(api: Api): Promise<Quote> {
    const thread = `pw-${Date.now().toString(36)}`
    const message = "给明理律所出一份 Qwen3-32B 私有化方案，50 人并发，预算 40 万以内"
    await api.sse("/api/agent/chat", { thread_id: thread, message })
    const stream = await api.sse("/api/agent/resume", { thread_id: thread, decision: "approve" })
    return artifactOf<Quote>(stream, "quote")
  }

  test("草稿报价调整折扣并保存：总价按后端重算", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const quote = await draftQuote(api)

    await loginAs(page, "sales")
    await page.goto(`/quotes/${quote.id}`)
    await page.locator("#quote-discount").fill("5")
    const save = page.getByRole("button", { name: "保存调整" })
    await expect(save).toBeVisible()
    await save.click()

    await expect
      .poll(async () => (await api.call<Quote>("GET", `/api/quotes/${quote.id}`)).discount_rate)
      .toBeCloseTo(0.05, 3)
    const saved = await api.call<Quote>("GET", `/api/quotes/${quote.id}`)
    expect(saved.total_price).toBeLessThan(quote.total_price)
  })

  test("打印页：正式报价单不显示成本和毛利", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const quote = await draftQuote(api)

    await loginAs(page, "sales")
    await page.goto(`/quotes/${quote.id}`)
    await page
      .getByRole("link", { name: "打印报价单" })
      .or(page.getByRole("button", { name: "打印报价单" }))
      .click()
    await expect(page).toHaveURL(new RegExp(`/quotes/${quote.id}/print`))
    await expect(page.getByText(quote.code).first()).toBeVisible()
    await expect(page.getByText("SalesPilot 演示公司").first()).toBeVisible()
    await expect(page.getByRole("button", { name: "打印 / 存为 PDF" })).toBeVisible()
    await expect(page.getByText("毛利")).toHaveCount(0)
    await expect(page.getByText("成本")).toHaveCount(0)
  })
})

test("v3：通知铃铛——销售提交超标报销后，主管收到待审批通知，点击跳转", async ({ page, request }) => {
  const sales = await Api.as(request, "sales")
  const draft = await entertainmentDraft(sales, 86_000, 4, uniq("通知测试"))
  await sales.upload(draft.id, "invoice", "invoice.pdf", "application/pdf", PDF)
  await sales.upload(draft.id, "receipt", "receipt.png", "image/png", PNG)
  await sales.call("POST", `/api/expenses/${draft.id}/submit`)

  await loginAs(page, "manager")
  await page.goto("/dashboard")
  const bell = page.getByRole("button", { name: /通知，\d+ 条未读/ })
  await expect(bell).toBeVisible()
  await bell.click()
  await page
    .getByText(new RegExp(`待审批.*${draft.code}`))
    .first()
    .click()
  await expect(page).toHaveURL(/\/expenses|\/approvals/)
})
