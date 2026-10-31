import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

async function authGet<T>(page: Page, path: string): Promise<T> {
  const token = await page.evaluate(() => localStorage.getItem("sp.token"))
  const res = await page.request.get(path, { headers: { Authorization: `Bearer ${token}` } })
  return ((await res.json()) as { data: T }).data
}

test("不经过 AI 新建报价：选客户和产品线，从目录加物料并改单价，再加一笔费用（创建接口模拟，不写库）", async ({
  page,
}) => {
  await loginAs(page, "sales")
  await page.goto("/quotes/new")
  // 创建成功后跳到一张已有报价的详情页（只读）
  const existing = await authGet<{ items: { id: string }[] }>(page, "/api/quotes?page_size=1")
  let sent: Record<string, unknown> | null = null
  await page.route("**/api/quotes", async (route) => {
    if (route.request().method() !== "POST") return route.fallback()
    sent = route.request().postDataJSON()
    await route.fulfill({ json: { code: 0, message: "ok", data: { id: existing.items[0].id, code: "Q-TEST" } } })
  })

  await expect(page.getByText("先选客户和产品线，再添加物料")).toBeVisible()
  await page.getByRole("combobox").filter({ hasText: "搜索并选择客户" }).click()
  await page.getByPlaceholder("输入客户名称…").fill("南山")
  await page.getByRole("option", { name: "南山教育集团" }).click()
  await expect(page.getByRole("combobox", { name: "产品线" })).not.toHaveText("选择产品线")

  const save = page.getByRole("button", { name: "创建报价单" })
  await expect(save).toHaveCount(0)
  await page.getByRole("combobox", { name: "添加物料" }).click()
  await page.getByRole("option").first().click()

  const items = page.getByRole("region", { name: "物料" })
  const price = items.getByLabel(/^单价：/).first()
  await price.fill("1000")
  await expect(items).toContainText("原价")
  await items
    .getByLabel(/^数量：/)
    .first()
    .fill("2")

  const extras = page.getByRole("region", { name: "额外费用" })
  await extras.getByRole("button", { name: "添加费用" }).click()
  await extras.getByLabel("费用名称 1").fill("上门安装")
  await extras.getByLabel("单价 1").fill("800")
  await expect(page.getByText("预估毛利率")).toBeVisible()
  // 单价压到远低于目录价：提交前就提示会进审批（和后端同一套规则）
  const hint = page.getByRole("status", { name: "审批预判" })
  await expect(hint).toContainText("提交后要主管审批")
  await expect(hint).toContainText("超出销售折扣权限")
  if (process.env.SHOT_DIR) await page.screenshot({ path: `${process.env.SHOT_DIR}/approval-hint.png`, fullPage: true })

  await save.click()
  await expect.poll(() => sent).not.toBeNull()
  const body = sent as unknown as {
    pack: string
    customer_id: string
    opportunity_id: string | null
    items: Record<string, unknown>[]
  }
  expect(body.pack).toBeTruthy()
  expect(body.customer_id).toBeTruthy()
  expect(body.opportunity_id).toBeNull()
  expect(body.items[0]).toMatchObject({ qty: 2, unit_price: 100000 })
  expect(body.items[1]).toMatchObject({ name: "上门安装", unit_price: 80000, qty: 1 })
  await expect(page).toHaveURL(new RegExp(`/quotes/${existing.items[0].id}$`))
})

test("报销被驳回：看到驳回原因，修改金额后保存，按钮变为「重新提交」（接口模拟，不写库）", async ({ page }) => {
  await loginAs(page, "sales")
  const reason = "人均超标，请按 4 人以内重新报"
  let put: Record<string, unknown> | null = null
  let detail: Record<string, unknown> | null = null
  await page.route(/\/api\/expenses\/[0-9a-f-]{36}$/, async (route) => {
    if (route.request().method() === "PUT") {
      put = route.request().postDataJSON()
      detail = { ...detail, amount: put!.amount }
      return route.fulfill({ json: { code: 0, message: "ok", data: detail } })
    }
    const res = await route.fetch()
    const body = await res.json()
    detail = detail ?? {
      ...body.data,
      status: "rejected",
      approvals: [
        {
          id: "a-1",
          status: "rejected",
          reason: "人均超标",
          approver: { id: "u-m", name: "李薇" },
          comment: reason,
          decided_at: "2026-10-30T10:00:00Z",
        },
      ],
    }
    await route.fulfill({ response: res, json: { ...body, data: detail } })
  })

  await page.goto("/expenses")
  await page
    .getByText(/^E-\d{4}-\d+$/)
    .locator("visible=true")
    .first()
    .click()
  const sheet = page.getByRole("dialog")
  await expect(sheet).toContainText("李薇驳回了这张报销")
  await expect(sheet).toContainText(reason)
  await expect(sheet.getByRole("button", { name: "重新提交" })).toBeVisible()

  await sheet.getByRole("button", { name: "修改" }).click()
  const amount = sheet.locator("#exp-amount")
  await expect(amount).not.toHaveValue("")
  await amount.fill("500")
  await sheet.getByRole("button", { name: "保存修改" }).click()
  await expect.poll(() => put).not.toBeNull()
  expect(put).toMatchObject({ amount: 50000 })
  await expect(sheet.getByRole("button", { name: "重新提交" })).toBeVisible()
})
