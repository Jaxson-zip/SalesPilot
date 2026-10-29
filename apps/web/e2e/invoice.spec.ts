import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

const item = (seq: number, name: string, extra: Record<string, unknown> = {}) => ({
  seq,
  name,
  amount: 40_500_000,
  due_date: "2026-11-30",
  paid: 0,
  status: "pending",
  overdue_days: 0,
  invoice_status: "none",
  invoice_type: null,
  invoice_no: null,
  invoiced_on: null,
  invoice_note: null,
  invoiced_unpaid_days: 0,
  ...extra,
})

const plan = (id: string, items: ReturnType<typeof item>[], unpaid = 0) => ({
  code: 0,
  message: "ok",
  data: {
    contract_id: id,
    code: "C-测试",
    amount: 81_000_000,
    paid_amount: 0,
    overdue_amount: 0,
    invoiced_unpaid_amount: unpaid,
    items,
    rule_ref: "《回款管理办法》",
  },
})

/** 模拟回款计划和开票接口（不改真实合同），记下开票请求 */
async function mockPlan(page: Page, items: ReturnType<typeof item>[], after: ReturnType<typeof item>[], unpaid = 0) {
  const calls: { url: string; body: Record<string, unknown> }[] = []
  await page.route(/\/api\/contracts\/[^/]+\/payment-plan(\/\d+\/invoice)?$/, async (route) => {
    const id = route.request().url().split("/contracts/")[1].split("/")[0]
    // 开票之后再拉取回款计划时返回开票后的数据
    if (route.request().method() === "GET")
      return route.fulfill({ json: calls.length ? plan(id, after, unpaid) : plan(id, items) })
    calls.push({ url: route.request().url(), body: route.request().postDataJSON() })
    return route.fulfill({ json: plan(id, after, unpaid) })
  })
  return calls
}

async function openFirstPlan(page: Page) {
  await page.goto("/contracts")
  await page
    .getByRole("button", { name: /^C-\d{4}-\d{3}$/ })
    .first()
    .click()
  await expect(page.getByRole("table", { name: "回款计划" })).toBeVisible()
}

test("开票：销售申请开票，选普票并写备注", async ({ page }) => {
  await loginAs(page, "sales")
  const calls = await mockPlan(
    page,
    [item(1, "预付款"), item(2, "到货验收款")],
    [
      item(1, "预付款", { invoice_status: "requested", invoice_type: "normal", invoice_note: "抬头 A" }),
      item(2, "到货验收款"),
    ],
  )
  await openFirstPlan(page)
  // 销售看不到「登记开票」
  await expect(page.getByRole("button", { name: "预付款登记开票" })).toHaveCount(0)
  await page.getByRole("button", { name: "预付款申请开票" }).click()
  await page.getByRole("combobox").last().click()
  await page.getByRole("option", { name: "增值税普通发票" }).click()
  await page.getByLabel("备注").fill("抬头 A")
  await page.getByRole("button", { name: "提交申请" }).click()
  await expect.poll(() => calls.length).toBe(1)
  expect(calls[0].url).toMatch(/payment-plan\/1\/invoice$/)
  expect(calls[0].body).toMatchObject({ action: "request", invoice_type: "normal", note: "抬头 A" })
  await expect(page.getByText("普票 · 抬头 A")).toBeVisible()
})

test("开票：主管登记发票号码，显示已开票未回款", async ({ page }) => {
  await loginAs(page, "manager")
  const calls = await mockPlan(
    page,
    [item(1, "预付款", { invoice_status: "requested", invoice_type: "special", invoice_note: "抬头 B" })],
    [
      item(1, "预付款", {
        invoice_status: "issued",
        invoice_type: "special",
        invoice_no: "No.888",
        invoiced_on: "2026-10-01",
        invoiced_unpaid_days: 28,
      }),
    ],
    40_500_000,
  )
  await openFirstPlan(page)
  await page.getByRole("button", { name: "预付款登记开票" }).click()
  await expect(page.getByText("申请备注：抬头 B")).toBeVisible()
  await page.getByRole("button", { name: "登记", exact: true }).click()
  await expect(page.getByText("请填写发票号码")).toBeVisible() // 没填号码不提交
  expect(calls).toHaveLength(0)
  await page.getByLabel("发票号码").fill("No.888")
  await page.getByRole("button", { name: "登记", exact: true }).click()
  await expect.poll(() => calls.length).toBe(1)
  expect(calls[0].body).toMatchObject({ action: "issue", invoice_no: "No.888", invoice_type: "special" })
  await expect(page.getByText("专票 No.888 · 开票 28 天未收齐")).toBeVisible()
  await expect(page.getByText("已开票未回款", { exact: true })).toBeVisible()
  await expect(page.getByText("¥405,000").first()).toBeVisible()
})
