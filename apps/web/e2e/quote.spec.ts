import { expect, test, type Page } from "@playwright/test"

import { Api, artifactOf, loginAs } from "./helpers"

interface QuoteOut {
  id: string
  code: string
  status: string
}
interface QuoteDetail extends QuoteOut {
  contract_id: string | null
}

/** 通过 Agent 生成一张草稿报价单（标准版 ¥372,000，毛利 29.4%，提交后自动审批通过） */
async function agentDraftQuote(api: Api): Promise<QuoteOut> {
  const thread = `pw-${Date.now().toString(36)}`
  const message = "给明理律所出一份 Qwen3-32B 私有化方案，50 人并发，预算 40 万以内"
  await api.sse("/api/agent/chat", { thread_id: thread, message })
  const stream = await api.sse("/api/agent/resume", { thread_id: thread, decision: "approve" })
  const quote = artifactOf<QuoteOut>(stream, "quote")
  expect(quote.status).toBe("draft")
  return quote
}

const actionButtons = ["提交", "发送客户", "客户接受", "客户拒绝"] as const

/** 不可逆操作要先在确认框里确认 */
async function confirmIn(page: Page, title: string, button: string): Promise<void> {
  const dialog = page.getByRole("alertdialog", { name: title })
  await expect(dialog).toBeVisible()
  await dialog.getByRole("button", { name: button }).click()
  await expect(dialog).toBeHidden()
}

/** 当前页面上可见的状态操作按钮 */
async function visibleActions(page: Page): Promise<string[]> {
  const shown: string[] = []
  for (const name of actionButtons) {
    if (await page.getByRole("button", { name, exact: true }).isVisible()) shown.push(name)
  }
  return shown
}

test("报价单状态按钮：只显示当前可用的操作，依次提交 → 发送客户 → 客户接受", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const quote = await agentDraftQuote(api)

  await loginAs(page, "sales")
  await page.goto(`/quotes/${quote.id}`)
  await expect(page.getByText(quote.code).first()).toBeVisible()

  // 草稿：只能提交
  await expect(page.getByText("草稿").first()).toBeVisible()
  expect(await visibleActions(page)).toEqual(["提交"])

  await page.getByRole("button", { name: "提交", exact: true }).click()
  await expect(page.getByText("已审批").first()).toBeVisible()
  await expect.poll(() => visibleActions(page)).toEqual(["发送客户"])

  await page.getByRole("button", { name: "发送客户", exact: true }).click()
  await confirmIn(page, "发送给客户", "确认发送")
  await expect(page.getByText("已发送客户").first()).toBeVisible()
  await expect.poll(async () => (await visibleActions(page)).sort()).toEqual(["客户拒绝", "客户接受"].sort())

  await page.getByRole("button", { name: "客户接受", exact: true }).click()
  await confirmIn(page, "标记为客户接受", "确认客户接受")
  await expect(page.getByText("已成交").first()).toBeVisible()
  await expect.poll(() => visibleActions(page)).toEqual([])

  const saved = await api.call<QuoteDetail>("GET", `/api/quotes/${quote.id}`)
  expect(saved.status).toBe("accepted")
  expect(saved.contract_id).toBeTruthy()
})

test("确认框点取消：报价单状态不变（防误操作）", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const quote = await agentDraftQuote(api)
  await api.call("POST", `/api/quotes/${quote.id}/submit`)

  await loginAs(page, "sales")
  await page.goto(`/quotes/${quote.id}`)
  await page.getByRole("button", { name: "发送客户", exact: true }).click()
  const dialog = page.getByRole("alertdialog", { name: "发送给客户" })
  await dialog.getByRole("button", { name: "取消" }).click()
  await expect(dialog).toBeHidden()
  expect((await api.call<QuoteOut>("GET", `/api/quotes/${quote.id}`)).status).toBe("approved")
})

test("客户拒绝：已发送的报价单变为已驳回，不再有操作按钮", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const quote = await agentDraftQuote(api)
  await api.call("POST", `/api/quotes/${quote.id}/submit`)
  await api.call("POST", `/api/quotes/${quote.id}/send`)

  await loginAs(page, "sales")
  await page.goto(`/quotes/${quote.id}`)
  await page.getByRole("button", { name: "客户拒绝", exact: true }).click()
  await confirmIn(page, "标记为客户拒绝", "确认客户拒绝")

  await expect(page.getByText("已驳回").first()).toBeVisible()
  await expect.poll(() => visibleActions(page)).toEqual([])
  expect((await api.call<QuoteOut>("GET", `/api/quotes/${quote.id}`)).status).toBe("rejected")
})
