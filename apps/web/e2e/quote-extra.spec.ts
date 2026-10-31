import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

test("草稿报价加额外费用：填名称、单价、成本后保存，请求带上这一行（接口模拟，不写库）", async ({ page }) => {
  await loginAs(page, "sales")
  let sent: { items: Record<string, unknown>[]; discount_rate: number } | null = null
  let detail: Record<string, unknown> | null = null

  // 打开销售自己的一张报价，页面上把它当成草稿（只改返回给页面的数据）
  await page.route(/\/api\/quotes\/[0-9a-f-]{36}$/, async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    body.data.status = "draft"
    detail = detail ?? body.data
    await route.fulfill({ response: res, json: { ...body, data: detail } })
  })
  await page.route(/\/api\/quotes\/[0-9a-f-]{36}\/items$/, async (route) => {
    sent = route.request().postDataJSON()
    const d = detail as { items: Record<string, unknown>[]; total_price: number }
    const extra = sent!.items.find((i) => String(i.sku).startsWith("extra-"))!
    detail = {
      ...d,
      total_price: d.total_price + Number(extra.unit_price),
      items: [
        ...d.items,
        {
          ...extra,
          category: "service",
          subtotal_cost: Number(extra.unit_cost),
          subtotal_price: Number(extra.unit_price),
        },
      ],
    }
    await route.fulfill({ json: { code: 0, message: "ok", data: detail } })
  })

  await page.goto("/quotes")
  await page.getByText("Q-2026-003", { exact: true }).first().click()
  const box = page.getByRole("region", { name: "额外费用" })
  await box.getByRole("button", { name: "添加费用" }).click()

  const save = page.getByRole("button", { name: "保存调整" })
  await expect(save).toBeDisabled()
  await box.getByLabel("费用名称 1").fill("加急实施费")
  await box.getByLabel("单价 1").fill("5000")
  await box.getByLabel("成本 1").fill("1200")
  await expect(box).toContainText("¥5,000")
  await save.click()

  await expect.poll(() => sent).not.toBeNull()
  const line = sent!.items.find((i) => String(i.sku).startsWith("extra-"))
  expect(line).toMatchObject({ qty: 1, name: "加急实施费", unit: "项", unit_price: 500000, unit_cost: 120000 })
  // 保存后重新载入：费用行还在，可以接着改
  await expect(box.getByLabel("费用名称 1")).toHaveValue("加急实施费")
  await expect(box.getByLabel("单价 1")).toHaveValue("5000")
})
